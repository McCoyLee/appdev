# AGENTS.md

## 项目类型

**数据流水线**。Python 3.11，GitHub Actions cron 定时跑，结果 commit 回 `data/` + 存 artifact。

## 文件结构

- `src/pipeline.py` — 三段式：`fetch()` 抓数据 / `transform()` 处理 / `save()` 输出
  - **业务逻辑改 `fetch` 和 `transform`**，`save` 一般不动
- `tests/test_pipeline.py` — 测 `transform`（不联网，CI 能稳定跑）
- `data/` — 输出目录（流水线 commit 到这里）
- `.github/workflows/ci.yml` — ruff + pytest
- `.github/workflows/run.yml` — cron 定时跑（默认北京 6:00）+ 提交结果 + artifact

## 修改约定

1. 抓取逻辑放 `fetch()`，返回 list[dict]
2. 处理逻辑放 `transform()`，返回最终 dict
3. **`transform` 必须不联网**（这样 CI 的 pytest 能稳定测），联网只在 `fetch`
4. 改 cron 时间：`run.yml` 里 `cron: "0 22 * * *"`（UTC，北京 +8h）
5. 大量数据建议存 artifact 而不是 commit（避免仓库膨胀）
6. 改完调 `run_ci`
