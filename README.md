# AI 造应用 · App For Oneself

让"有想法但没编程基础"的人，打开浏览器就能用 AI 给自己造小到工具、大到正经服务的应用。
项目代码、密钥、运行全部托管在用户自己的 GitHub 仓库 + GitHub Actions 上，本平台不存业务数据。

设计文档：[开发大纲.md](./开发大纲.md) ｜ 进度记录：[进度.md](./进度.md)

## 快速启动（开发期）

```bash
# 1. 后端
conda activate appdev
pip install -r requirements.txt
cp .env.example .env  # 填入 DEEPSEEK_API_KEY、GITHUB_TOKEN
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 2. 前端（另开终端）
cd frontend
npm install
npm run dev  # 默认 5173 端口
```

浏览器打开 `http://<server>:5173`。

## 目录速览

```
backend/   FastAPI 后端（AI agent + GitHub API + SSE）
frontend/  Vue 3 前端（用户界面）
templates/ 提供给用户 fork 的项目模板
scripts/   一次性运维脚本
docs/      面向用户的文档
```

## 开发约定

- 后端只做无状态代理与 agent 编排，**不存业务数据**
- 用户凭据（GITHUB_TOKEN、AI Key）来自前端，不在后端持久化
- AI 修改代码一律走 `ai/*` 分支 + PR，main 永远干净
- 改完同步追加进度到 [进度.md](./进度.md)
