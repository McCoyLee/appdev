# AGENTS.md

> 给 AI 看的项目说明。

## 项目类型

**FastAPI 后端 API**。Python 3.11，uvicorn 跑服务，pytest 测试。

## 文件结构

- `app/` — 业务代码（`main.py` 是入口）
- `tests/` — 测试（pytest 自动发现）
- `requirements.txt` — Python 依赖
- `.github/workflows/ci.yml` — 跑 ruff + pytest
- `.github/workflows/deploy.yml` — 推 main 后通过 Render Deploy Hook 部署

## 修改约定

1. 新路由放在 `app/` 下，可以拆 router；保持 `main.py` 是入口
2. 加依赖时同时更新 `requirements.txt`
3. **每加一个路由都写对应的 pytest**，放在 `tests/test_*.py`
4. 不引入 ORM/db 之前别假设有数据库（用 in-memory dict / sqlite 起步）
5. 不破坏 `ci.yml` 和 `deploy.yml`，除非用户明确要求
6. 修改完调一次 `run_ci`，确保 ruff + pytest 全绿

## 部署

push 到 main 触发 `deploy.yml`，调用 Render Deploy Hook。
用户首次启用：去 https://render.com 建 Web Service，把 Deploy Hook URL 放到仓库 secrets 的 `RENDER_DEPLOY_HOOK`。
