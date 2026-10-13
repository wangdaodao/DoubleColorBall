#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 data/ 下的双色球 JSON 数据。

发现问题时输出 GitHub 注解并以非 0 退出码终止，
避免把损坏的数据提交进仓库。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

DATA_DIR = Path("data")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 每年允许的最大缺号数（历史上有少量跳期属正常）
MAX_GAPS_PER_YEAR = 0


def err(msg: str) -> None:
    print(f"::error::{msg}")
    print(msg, file=sys.stderr)


def main() -> int:
    files = sorted(p for p in DATA_DIR.glob("*.json") if p.stem.isdigit())
    if not files:
        err("data/ 目录下没有年度数据文件")
        return 1

    problems: list[str] = []
    all_codes: dict[str, int] = {}
    total = 0

    for path in files:
        year = int(path.stem)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{path.name} 解析失败: {exc}")
            continue

        items = payload.get("data")
        if not isinstance(items, list) or not items:
            problems.append(f"{path.name} data 字段为空或格式错误")
            continue

        if payload.get("count") != len(items):
            problems.append(
                f"{path.name} count={payload.get('count')} "
                f"与实际条数 {len(items)} 不一致")

        seq: list[int] = []
        for it in items:
            total += 1
            code = str(it.get("code") or "")
            all_codes[code] = all_codes.get(code, 0) + 1

            if len(code) != 7 or not code.isdigit():
                problems.append(f"{path.name} 期号格式异常: {code!r}")
                continue
            if code[:4] != str(year):
                problems.append(f"{path.name} 期号 {code} 归属年份不符")

            red = it.get("red")
            if (not isinstance(red, list) or len(red) != 6
                    or any(not isinstance(x, int) for x in red)):
                problems.append(f"{code} red 字段异常: {red!r}")
            else:
                if len(set(red)) != 6:
                    problems.append(f"{code} 红球有重复: {red}")
                if any(not 1 <= x <= 33 for x in red):
                    problems.append(f"{code} 红球超出 1-33: {red}")
                if red != sorted(red):
                    problems.append(f"{code} 红球未升序: {red}")
                if it.get("sum") != sum(red):
                    problems.append(f"{code} 和值错误: "
                                    f"{it.get('sum')} != {sum(red)}")

            blue = it.get("blue")
            if not isinstance(blue, int) or not 1 <= blue <= 16:
                problems.append(f"{code} 蓝球异常: {blue!r}")

            d = str(it.get("date") or "")
            if not DATE_RE.match(d):
                problems.append(f"{code} 日期格式错误: {d!r}")
            else:
                try:
                    date.fromisoformat(d)
                except ValueError:
                    problems.append(f"{code} 日期非法: {d}")
                if d[:4] != str(year):
                    problems.append(f"{code} 日期 {d} 与年份 {year} 不符")

            try:
                seq.append(int(code[4:]))
            except ValueError:
                pass

        # 期号连续性
        if seq:
            missing = sorted(set(range(min(seq), max(seq) + 1)) - set(seq))
            if len(missing) > MAX_GAPS_PER_YEAR:
                problems.append(
                    f"{path.name} 期号不连续，缺 {len(missing)} 期: {missing[:10]}")

    # 全局重复检查
    dupes = [c for c, n in all_codes.items() if n > 1]
    if dupes:
        problems.append(f"存在重复期号: {sorted(dupes)[:10]}")

    # latest.json / index.json 与年度数据一致
    latest_path = DATA_DIR / "latest.json"
    if latest_path.exists():
        lat = json.loads(latest_path.read_text(encoding="utf-8"))
        if max(all_codes) != lat.get("latest", {}).get("code"):
            problems.append(
                f"latest.json({lat.get('latest', {}).get('code')}) "
                f"与最大期号({max(all_codes)})不一致")

    index_path = DATA_DIR / "index.json"
    if index_path.exists():
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        if idx.get("totalCount") != len(all_codes):
            problems.append(
                f"index.json totalCount={idx.get('totalCount')} "
                f"与实际 {len(all_codes)} 不一致")

    years = [int(p.stem) for p in files]
    print(f"校验完成：{len(years)} 个年份（{min(years)}~{max(years)}），"
          f"{total} 期")

    if problems:
        err(f"发现 {len(problems)} 个问题")
        for p in problems[:30]:
            err(p)
        if len(problems) > 30:
            err(f"...另有 {len(problems) - 30} 个问题未显示")
        return 1

    print("✅ 数据校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())