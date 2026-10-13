#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双色球开奖数据抓取器（按年存JSON）

数据源：中国福利彩票发行管理中心官方开奖公告接口
输出：data/<年份>.json + data/latest.json

设计要点
  - 按年请求（issueStart/issueEnd），规避单次返回上限，只增量抓当年
  - 幂等：内容与磁盘一致则不写文件，便于 Action 里判断"有无新数据"
  - 失败重试 + 退避；某一年失败不阻断其余年份
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = ("https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/"
       "findDrawNotice")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CST = timezone(timedelta(hours=8))
REQUEST_INTERVAL = 0.8  # 每年请求之间的间隔秒数
WEEK_EN = {"一": "Mon", "二": "Tue", "三": "Wed", "四": "Thu",
           "五": "Fri", "六": "Sat", "日": "Sun"}

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


# ---------------------------------------------------------------- 工具

def log(msg: str) -> None:
    print(f"[{datetime.now(CST):%H:%M:%S}] {msg}", flush=True)


def fetch_year(year: int, retries: int = 4, timeout: int = 60) -> list[dict]:
    """抓取某一年的全部期次，失败自动退避重试。"""
    url = (f"{API}?name=ssq&issueStart={year}001"
           f"&issueEnd={year}999&pageNo=1&pageSize=1000")
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("state") != 0:
                raise ValueError(f"接口返回 state={payload.get('state')} "
                                 f"message={payload.get('message')}")
            rows = payload.get("result") or []
            log(f"  {year}: 抓到 {len(rows)} 期")
            return rows
        except Exception as exc:  # noqa: BLE001 - 网络/接口异常统一重试
            last_err = exc
            if attempt < retries:
                wait = min(2 ** attempt + random.random(), 20)
                log(f"  {year}: 第 {attempt} 次失败({exc})，{wait:.1f}s 后重试")
                time.sleep(wait)
    raise RuntimeError(f"{year} 年数据抓取失败: {last_err}")


def normalize(row: dict) -> dict | None:
    """把官网原始记录转成精简字段；字段缺失返回 None。"""
    code = (row.get("code") or "").strip()
    raw_date = (row.get("date") or "").strip()
    m = DATE_RE.match(raw_date)
    if not code or not m:
        return None

    reds = [int(x) for x in (row.get("red") or "").split(",") if x.strip().isdigit()]
    blue_raw = (row.get("blue") or "").strip()
    if len(reds) != 6 or not blue_raw.isdigit():
        return None

    # 官网日期形如 "2026-10-11(日)"，括号内为中文星期
    cn_week = ""
    wm = re.search(r"[（(]([一二三四五六日])[)）]", raw_date)
    if wm:
        cn_week = wm.group(1)

    red = sorted(reds)
    return {
        "code": code,
        "date": f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
        "week": WEEK_EN.get(cn_week, ""),
        "red": red,
        "sum": sum(red),
        "blue": int(blue_raw),
    }


def build_year_file(rows: list[dict], year: int, updated_at: str,
                    old: dict | None) -> dict:
    """构造单个年度文件内容：按期号升序，字段顺序固定。

    若开奖数据本身未变化，则沿用旧的 updatedAt —— 保证文件内容稳定，
    避免定时任务每次都产生无意义提交。
    """
    items: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        item = normalize(row)
        if item is None or item["code"] in seen:
            continue
        seen.add(item["code"])
        items.append(item)
    items.sort(key=lambda x: x["code"])

    if old and old.get("data") == items:
        updated_at = old.get("updatedAt") or updated_at
    return {
        "year": year,
        "updatedAt": updated_at,
        "count": len(items),
        "latestIssue": items[-1]["code"] if items else None,
        "data": items,
    }


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - 文件缺失或损坏都按"无旧数据"处理
        return None


def write_json(path: Path, payload: dict) -> bool:
    """写入 JSON；内容无变化则不落盘。返回是否发生写入。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser(description="抓取双色球开奖数据并按年存 JSON")
    ap.add_argument("--data-dir", default="data", help="输出目录，默认 data")
    ap.add_argument("--start-year", type=int, default=2013,
                    help="起始年份，默认 2013（福彩官网接口最早年份）")
    ap.add_argument("--years-back", type=int, default=0,
                    help="仅刷新最近 N 年，0=全部年份（默认全量校验）")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    current_year = datetime.now(CST).year
    first_year = args.start_year
    if args.years_back > 0:
        first_year = max(args.start_year, current_year - args.years_back + 1)
    years = list(range(first_year, current_year + 1))

    # 已经存在文件的年份可以跳过（增量模式）；当年永远重抓
    todo = [y for y in years
            if y == current_year or not (data_dir / f"{y}.json").exists()]
    if not todo:
        log("所有年份均已是最新，跳过抓取")
        # 仍然校验一次 latest
        return sync_latest(data_dir, years, dry=True)

    log(f"待抓取年份: {todo[0]}~{todo[-1]}（共 {len(todo)} 个）")

    merged: dict[int, list[dict]] = {}
    failures: list[int] = []
    for year in todo:
        try:
            merged[year] = fetch_year(year)
        except Exception as exc:  # noqa: BLE001 - 单年失败不阻断整体
            log(f"  !! {exc}")
            failures.append(year)
        if year != todo[-1]:
            # 礼貌间隔，避免对官网接口造成压力
            time.sleep(REQUEST_INTERVAL)

    if failures:
        log(f"以下年份抓取失败（保留原有文件）: {failures}")

    updated_at = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    changed: list[str] = []
    for year in sorted(merged):
        path = data_dir / f"{year}.json"
        payload = build_year_file(merged[year], year, updated_at, read_json(path))
        if write_json(path, payload):
            changed.append(year)
            log(f"  已更新 {year}.json（{payload['count']} 期，"
                f"最新 {payload['latestIssue']}）")
        else:
            log(f"  {year}.json 无变化")

    if not merged:
        log("没有任何年份抓取成功，终止")
        return 1

    rc = sync_latest(data_dir, years, dry=False)
    if failures:
        # 部分年份失败时仍提交成功部分，但以非 0 退出码提示
        return 2
    return rc


def sync_latest(data_dir: Path, years: list[int], dry: bool) -> int:
    """汇总 latest.json 与 index.json。

    年份以磁盘上实际存在的年度文件为准，而非本次请求范围 ——
    这样 backfill 补出的 2003~2012 也能进入索引。
    """
    on_disk = sorted(
        int(p.stem) for p in data_dir.glob("*.json")
        if p.stem.isdigit() and len(p.stem) == 4
    )
    years = sorted(on_disk)

    all_items: list[dict] = []
    per_year: list[dict] = []
    for year in sorted(years):
        payload = read_json(data_dir / f"{year}.json")
        if not payload:
            continue
        all_items.extend(payload.get("data") or [])
        per_year.append({
            "year": year,
            "count": payload.get("count", 0),
            "latestIssue": payload.get("latestIssue"),
        })

    if not all_items:
        log("本地无任何年度数据，跳过汇总")
        return 1

    all_items.sort(key=lambda x: x["code"])
    latest = all_items[-1]
    now_ts = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    latest_path = data_dir / "latest.json"
    index_path = data_dir / "index.json"
    old_latest = read_json(latest_path) or {}
    old_index = read_json(index_path) or {}

    latest_body = {"count": len(all_items), "latest": latest}
    index_body = {
        "startYear": per_year[0]["year"],
        "endYear": per_year[-1]["year"],
        "totalCount": len(all_items),
        "years": per_year,
    }

    # 内容未变则沿用旧时间戳，保证文件稳定（否则每次运行都会产生空提交）
    latest_ts = (old_latest.get("updatedAt")
                 if {k: old_latest.get(k) for k in latest_body} == latest_body
                 else now_ts) or now_ts
    index_ts = (old_index.get("updatedAt")
                if {k: old_index.get(k) for k in index_body} == index_body
                else now_ts) or now_ts

    wrote_latest = write_json(latest_path, {"updatedAt": latest_ts, **latest_body})
    wrote_index = write_json(index_path, {"updatedAt": index_ts, **index_body})

    log(f"latest.json -> 第 {latest['code']} 期 "
        f"红球 {latest['red']} 蓝球 {latest['blue']:02d} "
        f"（和值 {latest['sum']}，{latest['date']}）")
    log(f"合计 {len(all_items)} 期，{per_year[0]['year']}~{per_year[-1]['year']}")

    if dry:
        return 0
    if wrote_latest:
        log("  latest.json 已更新")
    if wrote_index:
        log("  index.json 已更新")
    if not (wrote_latest or wrote_index):
        log("  无新期开奖")
    return 0


if __name__ == "__main__":
    sys.exit(main())