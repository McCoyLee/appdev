# CLAUDE.md — 项目接力文档

> 给接手开发的 AI/人看的导航。详细设计见 [开发大纲.md](./开发大纲.md)，逐步进度见 [进度.md](./进度.md)，测试见 [docs/testing.md](./docs/testing.md)，桌面端见 [docs/desktop.md](./docs/desktop.md)。

## 一句话

让没有编程基础的人在浏览器里用自然语言让 AI 改自己的 GitHub 仓库：AI 读/改代码 → 跑 GitHub Actions CI → 自动部署预览 → 用户点「就这版」一键采纳。后端无状态，一切真相在用户自己的 GitHub 仓库。

## 当前状态（截至 2026-05-31）

- **M0~M3 全部完成**（26 个任务）+ **M4-1~M4-4**（PR 协作 / PWA / diff / agent PR 工具）已做
- 后端 25 个端点（+`/api/prs` 6 个）/ AI 16 个工具（+list_prs/comment_pr/merge_pr）/ 前端 13 个组件（+PrPanel）/ 6 个模板 / Tauri 骨架（未编译）/ PWA（manifest+sw，可安装）
- M0~M3 已推送 `McCoyLee/appdev`（commit `e92462e`）；M4-1~M4-4 本地已提交，待推送

## 技术栈

- 后端：Python 3.11（conda 环境 `appdev`）+ FastAPI + httpx + sse-starlette + PyNaCl
- 前端：Vue 3 + Vite + Element Plus + Pinia
- AI：DeepSeek（OpenAI 兼容 function calling）
- 桌面：Tauri 2（src-tauri/，代码就位但本机无 Rust/webkit 无法编译）

## 启动开发环境

```bash
cd /home/limaocheng/app-for-oneself

# 后端（项目根，端口 8901）
conda run -n appdev uvicorn backend.app.main:app --host 0.0.0.0 --port 8901 --reload

# 前端（另开终端，端口 5173，已配 /api 代理到 8901）
cd frontend && npm run dev -- --host 0.0.0.0

# 或一键起两个：
bash scripts/dev.sh
```

凭据在 `.env`（已 gitignore）：`DEEPSEEK_API_KEY` / `GITHUB_TOKEN` / `TEST_REPO=McCoyLee/github-api-test`。
注意 `conda run` 必须在**项目根目录**执行（`backend.app.main` 是模块路径）。
服务器走 SOCKS 代理（httpx 需 `httpx[socks]`，已装）。

## 关键文件地图

```
backend/app/
├── main.py                 # FastAPI 入口，include 所有 router
├── core/config.py          # pydantic-settings 读 .env
├── api/
│   ├── deps.py             # 依赖注入：凭据 header 优先 > .env 兜底
│   ├── chat.py             # POST /api/chat —— SSE 流式 agent 对话（核心）
│   ├── projects.py         # 新建项目（create/init/create-stream）
│   ├── branches.py         # 采纳/丢弃 ai/* 分支（FF→rebase→merge 三级）
│   ├── prs.py              # M4 PR 协作：列表/详情(文件+CI+评论)/开/留言/合并/关闭
│   ├── preview.py          # 预览部署 + 一键放开 Pages 分支策略
│   ├── probe.py            # 凭据连通性探测（github/ai/repos）
│   ├── logs_stream.py      # workflow 日志 SSE 实时流
│   ├── repo.py secrets.py actions.py templates.py
├── ai/
│   ├── agent.py            # agent loop（async generator，产出 AgentEvent）
│   ├── tools.py            # 13 个工具的 schema + dispatcher（改工具看这里）
│   ├── prompts.py          # 中文 system prompt
│   ├── outline.py          # 项目符号索引（AST + 5 语言正则）
│   └── providers/          # base.py 协议 + deepseek.py
└── github/
    ├── client.py           # 异步 GitHubClient（所有 GitHub API 封装）
    └── errors.py

frontend/src/
├── App.vue                 # 顶栏 + 启动引导 + 解锁流程
├── views/Workspace.vue     # 左聊天 / 右标签页（预览/仓库/密码本/运行/模板）
├── components/
│   ├── ChatPanel.vue       # SSE 流式聊天 + tool 卡片 + PlanCard 渲染
│   ├── PreviewPanel.vue    # iframe 预览 + 就这版/丢弃
│   ├── PlanCard.vue        # 计划 checklist
│   ├── NewProjectDialog.vue RepoSwitcher.vue VaultDialog.vue
│   ├── UnlockDialog.vue    # 加密解锁
│   ├── PrPanel.vue         # M4 协作标签页：PR 列表 + 详情抽屉 + 提/评论/合并
│   ├── LogStreamDialog.vue RepoTree.vue SecretsPanel.vue RunsPanel.vue TemplatesPanel.vue
├── api/client.js           # axios + 拦截器注入凭据 header
├── api/chat.js             # fetch SSE 客户端
├── stores/vault.js         # localStorage 凭据（WebCrypto 加密，async）
├── stores/session.js       # 当前 repo/user/messages/currentBranch
└── utils/crypto.js         # PBKDF2 + AES-GCM

templates/                  # 6 个：static-site / api-server / cron-task / telegram-bot / flask-app / data-pipeline
src-tauri/                  # Tauri 2 桌面壳（lib.rs 管后端进程）
scripts/                    # smoke_*.py 烟雾测试 + init_template.py + dev.sh
```

## 核心工作流（理解这个就懂整个产品）

```
用户聊天 → POST /api/chat (SSE)
  → agent.py 循环：DeepSeek function calling
    → tools.py dispatch → github/client.py 调 GitHub API
    → 工具：get_project_outline / read_file / write_files / run_ci / propose_plan ...
  → AI 在 ai/<desc> 分支改代码，run_ci 跑 GitHub Actions 验证（失败自修复）
  → agent 结束自动 dispatch pages.yml 部署预览
  → 前端 PreviewPanel iframe 显示，用户二选一：
    A) 点「就这版」→ POST /api/branches/{branch}/adopt → FF（失败则 squash-rebase→FF→merge 兜底）
    B) 点「提个 PR」→ POST /api/prs → 走「协作」标签页 review/留言/合并（M4-1）
```

## 开发铁律（沿用）

1. 后端**无业务数据库**，重启不丢数据；一切存用户的 GitHub 仓库
2. 凭据来自前端 header（`X-GitHub-Token` / `X-AI-Key` / `X-Repo`），`.env` 仅开发兜底
3. AI 改代码一律走 `ai/*` 分支，main 永远稳定
4. 加工具：在 `backend/app/ai/tools.py` 加 schema + handler + 注册 HANDLERS
5. 加 provider：实现 `providers/base.py` 协议 + 在 `api/deps.py` 注册
6. 加模板：`templates/<id>/` 必须含 `template.json` + `AGENTS.md` + `ci.yml`
7. 改完代码：重启后端（无 --reload 时）；前端 Vite 自动 HMR
8. **每完成一步追加到 `进度.md`**；提交信息中文 + `Co-Authored-By: Claude`
9. 提交/推送 GitHub 用 `.env` 的 `GITHUB_TOKEN`（McCoyLee/appdev）；推送时临时把 token 塞进 remote URL，推完清掉

## 已知限制

1. Tauri 桌面端未编译验证（本服务器无 Rust + webkit2gtk + 无头）
2. PyInstaller sidecar 仅文档化，未实测
3. PAT 缺 `Environments`/`Repository creation` 权限时部分功能降级（有友好报错）
4. squash-rebase 采纳会丢 ai/* 中间 commit 历史（设计权衡）
5. 凭据加密：忘主密码不可恢复

## 下一步（M4 候选，见进度.md 末尾）

1. 桌面机上真编译 Tauri + PyInstaller sidecar，做到「双击即用」
2. ~~PR 列表 + 多人协作~~ ✅ M4-1 已做；可继续做 PR review（行内 comment / approve）
3. ~~移动端响应式 / PWA~~ ✅ M4-2 已做（手写 manifest+sw，可安装；窄屏堆叠）
4. 多用户 SaaS（用户隔离 + 配额 + 计费）
5. 国内 GitHub 加速反代内置

## 测试

见 [docs/testing.md](./docs/testing.md)。最快：`conda run -n appdev python scripts/smoke_agent.py` 跑通即核心链路 OK。
