# 双色球开奖数据（自动更新）

按年份分类存储的双色球历史开奖数据，通过 GitHub Actions 自动抓取、更新并发布。

- 数据范围：**2003 - 2026**，共 **3513 期**，每年一个 JSON 文件
- 更新频率：开奖日（周二 / 周四 / 周日）自动运行，另有次日补跑
- 在线浏览：仓库启用 GitHub Pages 后可在线查看（见下方"启用网页"）

## 数据结构

### `data/<年份>.json`

```json
{
  "year": 2026,
  "updatedAt": "2026-10-13T09:08:01+08:00",
  "count": 116,
  "latestIssue": "2026116",
  "data": [
    {
      "code": "2026116",
      "date": "2026-10-11",
      "week": "Sun",
      "red": [10, 19, 24, 27, 28, 33],
      "sum": 141,
      "blue": 12
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `code` | 期号，如 `2026116` |
| `date` | 开奖日期 `YYYY-MM-DD` |
| `week` | 星期（英文缩写） |
| `red` | 6 个红球，升序，范围 1-33 |
| `sum` | 红球和值（便于直接做走势分析） |
| `blue` | 蓝球，范围 1-16 |

年度文件内的期号按升序排列；`count` 为该年期数。

### `data/index.json`

各年度汇总：起止年份、总期数、每年期数与末期期号。

### `data/latest.json`

最新一期开奖结果，便于只想取一期的调用方直接读取。

## 使用方式

### 直接引用（raw）

```
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/data/2026.json
https://raw.githubusercontent.com/<用户名>/<仓库名>/main/data/latest.json
```

### 在代码中调用

```javascript
// 取最新一期
const res = await fetch(
  "https://raw.githubusercontent.com/<用户名>/<仓库名>/main/data/latest.json"
);
const { latest } = await res.json();
console.log(latest.code, latest.red, latest.blue);

// 取某一年的全部开奖
const y = await fetch(
  "https://raw.githubusercontent.com/<用户名>/<仓库名>/main/data/2026.json"
).then(r => r.json());
console.log(y.data.length); // 116
```

> 若担心 raw 缓存，可在 URL 后加时间戳：`<url>?t=${Date.now()}`。

## 本地运行

无需任何第三方依赖，仅用标准库，Python 3.9+ 即可。

```bash
# 抓取/更新数据（默认刷新当年，已有年度文件会跳过）
python scripts/fetch_ssq.py

# 只刷新最近 3 年
python scripts/fetch_ssq.py --years-back 3

# 全量校验所有年份
python scripts/fetch_ssq.py --start-year 2013

# 回填 2003~2012 历史数据（中彩网接口，官方接口无早年数据）
python scripts/backfill_history.py

# 校验数据完整性
python scripts/validate_data.py
```

本地预览网页（需经 HTTP 访问，直接双击 HTML 浏览器会拦截读取）：

```bash
python -m http.server 8000
# 打开 http://localhost:8000/site/
```

## 启用网页（GitHub Pages）

1. 仓库 **Settings → Pages → Build and deployment**
2. Source 选 **GitHub Actions**
3. 推送到 `main` 分支后，`部署网页` 任务会自动发布
4. 访问 `https://<用户名>.github.io/<仓库名>/`

Pages 由 `site/index.html` 提供，`data/` 会在发布时复制到站点根目录下。
若不想启用网页，删掉 workflow 里的 `pages` 任务即可，不影响数据更新。

## 数据来源

| 范围 | 来源 |
| --- | --- |
| 2013 至今 | 中国福利彩票发行管理中心官方开奖公告接口 |
| 2003 - 2012 | 中彩网公开历史开奖接口 |

脚本特性：

- **按年请求**（`issueStart`/`issueEnd`），规避单次返回上限
- **幂等**：数据无变化时不改文件、不产生提交，避免定时任务刷屏
- **退避重试**：失败自动重试，单个年份失败不影响其余年份
- **提交前校验**：号码范围、红球去重升序、和值一致、期号连续性

## 免责声明

本项目数据仅供研究与学习，不构成任何投注建议。彩票开奖为独立随机事件，
历史数据无法预测未来结果。请理性购彩。

## License

MIT