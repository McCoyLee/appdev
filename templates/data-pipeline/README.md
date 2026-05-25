# 数据流水线

定时抓数据、处理、把结果存回仓库 `data/` 目录。

## 怎么用

跟 AI 说你要抓什么、怎么处理，比如：
- "每天抓 Hacker News 前 30 条，按分数排序存 JSON"
- "抓某商品页价格，记录历史，画个趋势"
- "聚合几个 RSS，去重后存 markdown"

AI 改 `src/pipeline.py` 的 `fetch()` 和 `transform()` → 跑 CI → 你采纳 → 每天自动跑。

## 看结果

- 仓库 `data/latest.json`（每次跑自动更新）
- 或 Actions 运行页下载 `pipeline-output` artifact

## 本地跑

```bash
pip install -r requirements.txt
python -m src.pipeline
```
