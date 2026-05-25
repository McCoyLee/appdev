# AGENTS.md

## 项目类型

**Flask web 应用**。Python 3.11，gunicorn 跑生产，pytest 测试，部署到 Render。

## 文件结构

- `app.py` — Flask 入口（`app` 对象 + 路由）
- `tests/test_app.py` — pytest（用 `app.test_client()`）
- `requirements.txt` — 依赖
- `Procfile` — Render/Heroku 启动命令（gunicorn）
- `.github/workflows/ci.yml` — ruff + pytest
- `.github/workflows/deploy.yml` — push main 触发 Render 部署

## 修改约定

1. 路由加在 `app.py`，复杂了可拆 blueprint，但保持 `app` 对象是入口
2. **每个路由配 pytest**（用 test_client）
3. 模板可以用 `render_template_string` 内联，或建 `templates/` 用 `render_template`
4. 加依赖同步 `requirements.txt`；改启动命令同步 `Procfile`
5. 改完调 `run_ci` 确保 ruff + pytest 绿
