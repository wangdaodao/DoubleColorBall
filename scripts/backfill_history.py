#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""双色球历史数据回填（2003-2012）

福彩官网接口最早只提供 2013 年及以后的数据，本脚本改用中彩网公开接口
补齐 2003~2012，输出格式与 fetch_ssq.py 完全一致。

说明：这是一次性/低频脚本，Action 默认不运行它。
日常更新只需要 fetch_ssq.py（见 workflows/update.yml）。
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://jc.zhcw.com/port/client_json.php"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Referer": "https://www.zhcw.com/",
    "Accept": "*/*",
}

CST = timezone(timedelta(hours=8))
WEEK_EN = {"一": "Mon", "二": "Tue", "三": "Wed", "四": "Thu",
           "五": "Fri", "六": "Sat", "日": "Sun"}

# 双色球 2003 年首期为 2003001
FIRST_ISSUE = 2003001
LAST_ISSUE = 2012156  # 2012 年末期，2013 起由官网接口接管


def log(msg: str) -> None:
    print(f"[{datetime.now(CST):%H:%M:%S}] {msg}", flush=True)


def fetch_page(page_no: int, page_size: int = 500,
               retries: int = 4, timeout: int = 60) -> dict:
    url = (f"{API}?transactionType=10001001&lotteryId=1&issueCount=0"
           f"&startIssue={FIRST_ISSUE}&endIssue={LAST_ISSUE}"
           f"&startDate=&endDate=&type=1&pageNum={page_no}&pageSize={page_size}")
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries:
                wait = min(2 ** attempt + random.random(), 20)
                log(f"  第 {page_no} 页第 {attempt} 次失败({exc})，{wait:.1f}s 后重试")
                time.sleep(wait)
    raise RuntimeError(f"第 {page_no} 页抓取失败: {last_err}")


def normalize(row: dict) -> dict | None:
    issue = str(row.get("issue") or "").strip()
    open_time = str(row.get("openTime") or "").strip()
    front = str(row.get("frontWinningNum") or "").strip()
    back = str(row.get("backWinningNum") or "").strip()

    reds = [int(x) for x in front.replace(",", " ").split() if x.strip().isdigit()]
    if len(issue) != 7 or not issue.isdigit() or len(reds) != 6 or not back.isdigit():
        return None

    red = sorted(reds)
    week_cn = (str(row.get("week") or "").strip() or "").lstrip("星期")
    return {
        "code": issue,
        "date": open_time,
        "week": WEEK_EN.get(week_cn, ""),
        "red": red,
        "sum": sum(red),
        "blue": int(back),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="回填双色球 2003-2012 历史数据")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--force", action="store_true",
                    help="已存在年度文件时也重新抓取")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    log("抓取中彩网历史数据 2003~2012 ...")
    rows: list[dict] = []
    first_page = fetch_page(1)
    total = int(first_page.get("total") or 0)
    rows.extend(first_page.get("data") or [])
    pages = int(first_page.get("pages") or 1)
    log(f"  共 {total} 期 / {pages} 页")
    for pn in range(2, pages + 1):
        rows.extend(fetch_page(pn).get("data") or [])
        log(f"  第 {pn}/{pages} 页完成（累计 {len(rows)} 期）")
        time.sleep(0.6)

    # 按年份分组
    by_year: dict[int, list[dict]] = {}
    for row in rows:
        item = normalize(row)
        if item is None:
            continue
        by_year.setdefault(int(item["code"][:4]), []).append(item)

    updated_at = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    for year in sorted(by_year):
        path = data_dir / f"{year}.json"
        if path.exists() and not args.force:
            log(f"  {year}.json 已存在，跳过（--force 可覆盖）")
            continue
        items = sorted(by_year[year], key=lambda x: x["code"])
        payload = {
            "year": year,
            "updatedAt": updated_at,
            "count": len(items),
            "latestIssue": items[-1]["code"],
            "data": items,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        log(f"  已写入 {year}.json（{len(items)} 期，"
            f"{items[0]['code']}~{items[-1]['code']}）")

    log(f"回填完成：{len(by_year)} 个年份，{len(rows)} 期")
    return 0


if __name__ == "__main__":
    sys.exit(main())