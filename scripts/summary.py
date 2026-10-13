#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 GitHub Actions 运行摘要（Markdown）。

输出到 stdout，由workflow 重定向进 $GITHUB_STEP_SUMMARY。
任何异常都只输出提示，不让摘要步骤拖垮整个任务。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))


def main() -> None:
    data = Path("data")
    try:
        latest = json.loads((data / "latest.json").read_text(encoding="utf-8"))
        index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"### 双色球数据\n\n读取数据失败：{exc}")
        return

    it = latest["latest"]
    reds = " ".join(f"{n:02d}" for n in it["red"])
    w = {"Mon": "周一", "Tue": "周二", "Wed": "周三", "Thu": "周四",
         "Fri": "周五", "Sat": "周六", "Sun": "周日"}

    print("### 双色球开奖数据\n")
    print(f"| 项目 | 内容 |")
    print(f"| --- | --- |")
    print(f"| 最新期号 | **{it['code']}** |")
    print(f"| 开奖日期 | {it['date']} {w.get(it['week'], '')} |")
    print(f"| 红球 | `{reds}` |")
    print(f"| 蓝球 | `{it['blue']:02d}` |")
    print(f"| 红球和值 | {it['sum']} |")
    print(f"| 数据范围 | {index['startYear']} - {index['endYear']}"
          f"（{len(index['years'])} 个年份 / {index['totalCount']} 期）|")
    print(f"| 最近更新 | {index['updatedAt']} |")
    print(f"| 生成时间 | {datetime.now(CST):%Y-%m-%d %H:%M:%S} (UTC+8) |\n")

    years = index["years"]
    if years:
        print("<details><summary>各年份期数</summary>\n")
        print("| 年份 | 期数 | 末期 |")
        print("| --- | --- | --- |")
        for y in years:
            print(f"| {y['year']} | {y['count']} | {y['latestIssue']} |")
        print("\n</details>\n")

    print("<sub>数据来源：中国福利彩票发行管理中心官方开奖公告"
          "（官网不可达时自动切换 17500 备用源）。"
          "本项目仅供数据研究，不构成投注建议。</sub>")


if __name__ == "__main__":
    main()