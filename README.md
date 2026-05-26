# AI 造应用 · App For Oneself

让没有编程基础的人，打开浏览器就能用自然语言让 AI 给自己造应用——小到一个工具页面，大到带后端 + CI + 定时任务的正经项目。所有代码、运行、密钥都托管在用户**自己的** GitHub 仓库 + GitHub Actions 上，本平台不存任何业务数据。

> 📖 文档导航：
> [CLAUDE.md](./CLAUDE.md) 项目接力/导航 ·
> [开发大纲.md](./开发大纲.md) 设计 ·
> [进度.md](./进度.md) 逐步进度 ·
> [docs/testing.md](./docs/testing.md) 测试验收 ·
> [docs/desktop.md](./docs/desktop.md) 桌面端 ·
> [docs/roadmap.md](./docs/roadmap.md) 未来计划

---

## 目录

- [它能做什么](#它能做什么)
- [架构总览](#架构总览)
- [环境要求](#环境要求)
- [快速上手（5 步）](#快速上手5-步)
  - [1. 拉代码 + 装依赖](#1-拉代码--装依赖)
  - [2. 准备凭据](#2-准备凭据)
  - [3. 配置 .env](#3-配置-env)
  - [4. 启动后端 + 前端](#4-启动后端--前端)
  - [5. 初始化模板 + 在浏览器跑一遍](#5-初始化模板--在浏览器跑一遍)
- [GitHub PAT 权限清单](#github-pat-权限清单)
- [Pages 一次性配置](#pages-一次性配置)
- [使用流程：从一句话到上线](#使用流程从一句话到上线)
- [项目结构](#项目结构)
- [扩展开发](#扩展开发)
  - [新增 AI provider](#新增-ai-provider)
  - [新增工具](#新增工具)
  - [新增模板](#新增模板)
- [API 端点速查](#api-端点速查)
- [SSE 事件类型](#sse-事件类型)
- [常见问题](#常见问题)
- [安全提醒](#安全提醒)

---

## 它能做什么

举几个真实任务（已实测）：

- **静态网页**："做一个个人主页，深色风格，加项目展示区"
- **后端 API**："做一个待办接口，SQLite 存储 + JWT 登录"
- **定时任务**："每天早上 7 点抓 36 氪头条，整理后发到我邮箱"
- **代码修复**："`ai/broken-xxx` 分支 CI 挂了，看日志修一下"

用户做的事：**打字**。其余 AI 自己干 — 读代码、改代码、跑测试、看日志、修错误、部署到 GitHub Pages / Render / 自己 VPS。

---

## 架构总览

```
浏览器（Vue 3 SPA）
   │
   │  REST + SSE（携带用户凭据 header）
   ▼
FastAPI 后端（无业务数据库）
   ├─ AI Agent Loop（读/改文件 → 跑 CI → 看日志 → 自修复）
   ├─ GitHub API 封装（异步 + 多用户）
   └─ 模板服务（列出模板 + 给 AI 读 AGENTS.md）
   │
   ▼
GitHub 仓库（用户自己的）
   ├─ 代码 + ai/* 分支
   ├─ Secrets / Variables（密钥库）
   ├─ Actions（CI / 部署 / cron 跑批）
   └─ Pages / Render / VPS（运行时）
```

**核心设计原则**

- 后端**完全无状态**，重启不丢任何用户数据
- 用户凭据只存浏览器 localStorage（M2 加 WebCrypto 加密）
- AI 修改一律走 `ai/*` 分支，main 永远稳定
- 每次对话结束自动派发预览，用户看到效果再点「就这版」一键采纳

---

## 环境要求

| 软件 | 版本 | 用途 |
|---|---|---|
| Python | ≥ 3.11 | 后端 |
| Node | ≥ 18（推荐 20+） | 前端 |
| Git | 任意现代版本 | 代码管理 |
| GitHub 账号 + PAT | fine-grained 推荐 | 推代码、跑 Actions、管 Secrets |
| DeepSeek 账号 + API Key | 任意 | AI 模型（其他 provider 后续支持） |

服务器 vs 本地：项目设计成可服务器部署（一份后端给多人用），开发期跑本地也完全 OK。

---

## 快速上手（5 步）

### 1. 拉代码 + 装依赖

```bash
git clone https://github.com/McCoyLee/appdev.git
cd appdev

# Python 后端依赖（推荐用 venv 或 conda 隔离）
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 或者用 conda：
# conda create -n appdev python=3.11 -y && conda activate appdev
# pip install -r requirements.txt

# Node 前端依赖
cd frontend
npm install
cd ..
```

### 2. 准备凭据

需要两样东西：

#### 2.1 GitHub PAT（fine-grained，推荐）

打开 https://github.com/settings/personal-access-tokens 点 **Generate new token (fine-grained)**：

- Token name：随便起，比如 `app-for-oneself-dev`
- Expiration：自定（建议 90 天起）
- **Repository access**：选 "All repositories"，或把要操作的仓库全选上
- **Repository permissions**（详见 [PAT 权限清单](#github-pat-权限清单)）：

  必选 R/W：`Contents` / `Pull requests` / `Actions` / `Workflows` / `Secrets`
  推荐 R/W：`Environments`（一键放开 Pages 分支限制要用）
  必选 R：`Metadata`

生成后**立刻复制 token**，关页面就再也看不到了。

#### 2.2 DeepSeek API Key

去 https://platform.deepseek.com → 注册账号 → 充值（¥10 够玩很久）→ `API Keys` 创建 → 复制 `sk-...` 开头的 key。

### 3. 配置 .env

```bash
cp .env.example .env
```

编辑 `.env`，至少填三项：

```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx          # 2.2 拿到的
GITHUB_TOKEN=github_pat_xxxxxxxxxxxxxx     # 2.1 拿到的
TEST_REPO=YourGitHubName/test-repo          # 一个可丢弃的测试仓库（必须已建好）
```

> `.env` 已被 `.gitignore` 排除，不会被推到 GitHub。

### 4. 启动后端 + 前端

**后端**（项目根目录，venv/conda 已激活）：

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8901 --reload
```

成功标志：日志末尾出现 `Application startup complete.`。新开终端验证：

```bash
curl http://127.0.0.1:8901/healthz
# {"status":"ok","env":"dev","deepseek_configured":true,"github_configured":true}
```

**前端**（另起一个终端）：

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

输出会显示访问地址，类似 `Local: http://localhost:5173/`。

### 5. 初始化模板 + 在浏览器跑一遍

#### 5.1 推模板到测试仓库

第一次用，先把一个模板的内容推到你的 `TEST_REPO` 当起点：

```bash
# 默认推 static-site
python scripts/init_template.py

# 或者切换模板
python scripts/init_template.py api-server
python scripts/init_template.py cron-task
```

> 这会**覆盖** `TEST_REPO` 的 main 分支内容。M2 之后会改成"创建新仓库 → 推模板"工作流，目前手动跑。

#### 5.2 打开浏览器

访问 `http://localhost:5173`，你会看到：

- **顶栏**：你的 GitHub 头像、仓库名 + 默认分支、`DeepSeek ✓` `GitHub ✓` 徽章、右上角【凭据】按钮
- **左边**：聊天框（输入区 + 历史消息）
- **右边**：5 个 tab：**预览** / 仓库 / 密码本 / 运行 / 模板

#### 5.3 跑第一个任务

在聊天框输入：

> 把首页标题改成「我的第一个 AI 项目」，背景加一点浅蓝色。

观察 AI 干的事（实时流式显示）：

1. `read_file` 看 index.html 和 style.css 当前内容
2. `ensure_branch` 建一个 `ai/xxx` 分支
3. `write_file` 改文件
4. `run_ci` 跑 GitHub Actions CI（实跑 ~10 秒）
5. CI 通过 → 系统自动派发 Pages 部署（事件 `preview_triggered`）
6. 右边「预览」tab 的 iframe 几十秒后自动刷新出新页面
7. 点【就这版】 → 后端 FF merge `ai/*` → main，删 `ai/*`，重派 main 部署

不满意？点【丢弃】，分支删除，回到 main 状态。
继续改？聊天框接着说，AI 会在**同一个** `ai/*` 上续 commit。

---

## GitHub PAT 权限清单

遇到 403 报错时对照这张表检查：

| Permission | 用途 | 必要性 |
|---|---|---|
| Metadata (R) | 读仓库元信息 | ✅ 必选 |
| Contents (R/W) | 读写代码、commit、push、合并分支 | ✅ 必选 |
| Pull requests (R/W) | 开 PR、查 PR、关 PR | ✅ 必选 |
| Actions (R/W) | 触发 workflow、查 run、读 logs | ✅ 必选 |
| Workflows (R/W) | 改 `.github/workflows/*.yml` | ✅ 必选 |
| Secrets (R/W) | 管理仓库 Secrets（密码本） | ✅ 必选 |
| Variables (R/W) | 管理普通环境变量 | ⭕ 推荐 |
| Environments (R/W) | 一键放开 Pages 分支策略 | ⭕ 推荐 |
| Administration (R/W) | 改仓库设置（M2 用） | ⏳ 暂不用 |

> Fine-grained PAT 是按仓库授权的——记得在 **Repository access** 里勾上要让 AI 改的仓库（或者选 All repositories）。

---

## Pages 一次性配置

每个新仓库第一次启用需要做两步（一次到位之后再也不用碰）：

### 1. 启用 GitHub Pages

进入仓库 `Settings → Pages`（URL：`https://github.com/<你>/<仓库>/settings/pages`）：

- **Source**：选 **GitHub Actions**

> 不要选 "Deploy from a branch"——那个模式不支持 ai/* 分支预览。

### 2. 放开 Pages 分支限制

默认 GitHub 只允许 main 分支部署到 Pages，所以 `ai/*` 分支首次部署会失败。改它：

**方法 A（推荐，UI 一键）**：在预览面板看到部署失败时，点出现的 【一键放开限制】 按钮。需要 PAT 有 `Environments` 权限。

**方法 B（手动）**：进入 `Settings → Environments → github-pages`：

- 找到 **Deployment branches and tags**
- 选 **No restriction**
- 保存

之后 AI 在任何 `ai/*` 分支上的预览都能跑了。

---

## 使用流程：从一句话到上线

完整一轮交互的内部步骤：

| # | 用户视角 | 系统视角 |
|---|---|---|
| 1 | 「把首页加深色模式」 | — |
| 2 | 看到 AI 列出 1-3 行计划 | AI 输出 plan |
| 3 | 看到聊天里 tool 卡片实时滚 | `read_file` × N 看上下文 |
| 4 | — | `ensure_branch` 建 `ai/dark-mode-xxx` |
| 5 | — | `write_files` 一个 commit 多个文件 |
| 6 | 看到「运行中…」徽章 | `run_ci` 阻塞等结果（10–60s）|
| 7 | （失败时）看到 AI 自己分析日志再改 | 拉 failed job logs tail → 再 write → 再 run_ci |
| 8 | 顶栏出现 `ai/dark-mode-xxx` 橙色徽章 | agent.run 结束自动 dispatch pages.yml |
| 9 | 右边 iframe 几十秒后自动刷新 | Pages 部署完成 |
| 10 | 点【就这版】 | `/api/branches/{branch}/adopt`：FF merge → 删 ai/* → 重派 main |
| 11 | 顶栏恢复成只显示 main | 预览 URL 现在是 main 内容 |

整个过程**用户从未碰 GitHub 网页、没碰过 PR、没碰过 YAML、没碰过命令行**。

---

## 项目结构

```
appdev/
├── backend/
│   └── app/
│       ├── main.py             # FastAPI 入口 + CORS + lifespan
│       ├── core/
│       │   ├── config.py       # pydantic-settings 读 .env
│       │   └── logging.py      # loguru 彩色日志
│       ├── api/                # REST + SSE 端点
│       │   ├── deps.py         # 依赖注入（header > .env）
│       │   ├── repo.py         # /api/repo/{info,tree,file}
│       │   ├── secrets.py      # /api/secrets CRUD
│       │   ├── actions.py      # /api/workflows, /api/runs
│       │   ├── preview.py      # /api/preview/* 部署相关
│       │   ├── branches.py     # /api/branches/* 采纳/丢弃
│       │   ├── templates.py    # /api/templates 元信息
│       │   └── chat.py         # /api/chat SSE 流式对话
│       ├── ai/
│       │   ├── providers/
│       │   │   ├── base.py     # Provider 协议
│       │   │   └── deepseek.py # OpenAI 兼容
│       │   ├── tools.py        # 工具 schema + dispatcher
│       │   ├── prompts.py      # system prompt（中文）
│       │   └── agent.py        # agent loop (async generator)
│       └── github/
│           ├── client.py       # 异步 GitHubClient 全套封装
│           └── errors.py       # GitHubError 子类
│
├── frontend/
│   ├── index.html
│   ├── vite.config.js          # dev proxy /api → 8901
│   └── src/
│       ├── main.js
│       ├── App.vue             # 顶栏 + 启动引导
│       ├── views/
│       │   └── Workspace.vue   # 左聊天 / 右标签页
│       ├── components/
│       │   ├── ChatPanel.vue       # SSE 流式聊天
│       │   ├── PreviewPanel.vue    # iframe 预览 + 采纳按钮
│       │   ├── RepoTree.vue        # 仓库浏览
│       │   ├── SecretsPanel.vue    # 密码本 CRUD
│       │   ├── RunsPanel.vue       # workflow 运行
│       │   ├── TemplatesPanel.vue  # 模板列表
│       │   └── VaultDialog.vue     # 凭据配置
│       ├── api/
│       │   ├── client.js       # axios + 拦截器注入凭据头
│       │   └── chat.js         # fetch SSE 客户端
│       └── stores/
│           ├── session.js      # 当前 repo/user/messages/branch
│           └── vault.js        # localStorage 凭据保险箱
│
├── templates/                  # 给用户用的项目模板
│   ├── static-site/            # HTML + CSS + JS → Pages
│   ├── api-server/             # FastAPI + pytest + Render
│   └── cron-task/              # Python 定时任务 + 邮件
│
├── scripts/
│   ├── init_template.py        # 推模板到 TEST_REPO
│   ├── smoke_github.py         # GitHub 封装层测试
│   ├── smoke_agent.py          # AI agent 端到端
│   └── smoke_sse.py            # SSE 流测试
│
├── .env.example
├── requirements.txt
├── README.md
├── 开发大纲.md                  # 设计稿
└── 进度.md                     # M0/M1 进度日志
```

---

## 扩展开发

### 新增 AI provider

想接入 Kimi / 通义千问 / Claude？三步：

1. **实现 provider 类**。在 `backend/app/ai/providers/` 加 `kimi.py`：

   ```python
   from .base import AssistantMessage, ToolCall

   class KimiProvider:
       name = "kimi"
       def __init__(self, api_key, base_url, model): ...

       async def chat(self, messages, tools=None, temperature=0.2) -> AssistantMessage:
           # 调你的 SDK，返回 AssistantMessage(content, tool_calls, finish_reason, usage)
           ...

       async def aclose(self): ...
   ```

2. **注册到依赖注入**。`backend/app/api/deps.py` 的 `require_provider` 里加分支：

   ```python
   if provider_name == "kimi":
       return _provider_singleton("kimi", api_key, base_url, model)
   ```

   并扩展 `_provider_singleton` 创建逻辑。

3. **前端凭据对话框**（`VaultDialog.vue`）开放 provider 选项。

### 新增工具

工具 = LLM 能调用的函数。两步：

1. **加 schema**（`backend/app/ai/tools.py` 的 `TOOL_SCHEMAS`）：

   ```python
   {
       "type": "function",
       "function": {
           "name": "deploy_to_vercel",
           "description": "把当前分支部署到 Vercel；什么场景使用",
           "parameters": {
               "type": "object",
               "properties": {
                   "branch": {"type": "string"},
                   "production": {"type": "boolean", "default": False},
               },
               "required": ["branch"],
           },
       },
   },
   ```

2. **实现 handler + 注册**：

   ```python
   async def _deploy_to_vercel(gh: GitHubClient, repo: str, args: dict) -> Any:
       branch = args["branch"]
       # 你的实现，可能调用 GitHubClient 方法 + 外部 API
       return {"deployed": True, "url": "https://..."}

   HANDLERS["deploy_to_vercel"] = _deploy_to_vercel
   ```

> 工具内部 raise `ValueError` 或 `GitHubError` 会被 dispatcher 转成 `{ok: false, error: "..."}`，AI 看到后会自己反思。

### 新增模板

在 `templates/` 下建子目录，必须包含：

- `template.json`：id / name / description / required_secrets / deploy_target
- `AGENTS.md`：**写给 AI 看的项目契约**（最关键）
- `README.md`：给用户看的使用说明
- `.github/workflows/ci.yml`：定义"什么算改对了"
- 业务代码本身

`AGENTS.md` 写得越具体 AI 越靠谱，至少包括：

- 项目类型 / 文件结构
- 修改约定（如"加路由必须配 pytest"、"不引入构建工具"）
- 部署机制（main push 触发什么 workflow）

> 看 `templates/api-server/AGENTS.md` 当样板。

---

## API 端点速查

所有请求可携带 header 覆盖 `.env`（前端通过 vault store 自动注入）：

| Header | 用途 |
|---|---|
| `X-GitHub-Token` | 用户的 GitHub PAT |
| `X-AI-Provider` | `deepseek`（其他后续支持） |
| `X-AI-Key` | 用户的 AI API key |
| `X-AI-Model` | 模型名（可选） |
| `X-Repo` | 仓库 owner/name（也可用 query `?repo=`） |

端点表：

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/healthz` | 健康检查 |
| GET | `/api/repo/info` | 当前仓库元信息 |
| GET | `/api/repo/tree?path=&ref=` | 列目录 |
| GET | `/api/repo/file?path=&ref=` | 读文件内容 |
| GET | `/api/secrets` | 列 secrets（仅名字） |
| POST | `/api/secrets` | 创建/更新 `{name, value}` |
| DELETE | `/api/secrets/{name}` | 删 secret |
| GET | `/api/workflows` | 列 workflows |
| GET | `/api/runs?workflow=&per_page=` | 列运行记录 |
| POST | `/api/runs/dispatch` | 触发 `{workflow, ref, inputs}` |
| GET | `/api/preview?branch=` | 预览部署状态 |
| POST | `/api/preview/trigger?branch=` | 手动派发预览 |
| POST | `/api/preview/setup-environment` | 一键放开 Pages 分支限制 |
| GET | `/api/branches` | 列 `ai/*` 分支 |
| POST | `/api/branches/{branch}/adopt` | 采纳到 main（FF 优先） |
| POST | `/api/branches/discard` | 丢弃 `{branch}` |
| GET | `/api/templates` | 列可用模板 |
| GET | `/api/templates/{id}` | 单个模板详情 |
| POST | `/api/chat` (SSE) | 流式对话，事件见下 |

---

## SSE 事件类型

`POST /api/chat` 流式返回的事件（前端按需渲染）：

| event | data 字段 | 含义 |
|---|---|---|
| `assistant_text` | `{content}` | AI 输出的一段文本（增量） |
| `tool_call` | `{id, name, arguments}` | AI 决定调某工具 |
| `tool_result` | `{id, name, payload}` | 工具执行完成；`payload={ok, result|error}` |
| `preview_triggered` | `{branch, workflow}` | agent 结束自动派发了预览 |
| `preview_error` | `{branch, message}` | 派发失败 |
| `usage` | `{prompt_tokens, completion_tokens, total_tokens}` | 累计 token |
| `done` | `{finish_reason}` | 对话结束 |
| `error` | `{message}` | 出错（一般是 LLM 调用挂） |

---

## 常见问题

**Q: `setup-environment` 返回 403**
A: PAT 缺 `Environments` 写权限。两个解法：编辑 PAT 加上这个权限，或手动去 `Settings → Environments → github-pages` 把 Deployment branches 改 No restriction。

**Q: Pages 部署失败 "Branch is not allowed to deploy to github-pages"**
A: 同上，分支限制问题。预览面板的错误横幅会显示解决按钮和链接。

**Q: CI 第一次跑得很慢**
A: `actions/setup-python` 第一次要拉镜像，10–30 秒。之后命中缓存几秒。

**Q: AI 反复修同一个文件 / 自我纠结**
A: 文件太大时 LLM 复制原文会出错。对策：
- 让 AI 用 `read_file` 的 `start_line`/`end_line` 切片读
- 用 `write_files` 一次性多文件原子提交
- M2 会加 tree-sitter 符号索引

**Q: 让 AI 处理多文件大改动**
A: 提示词里明确说"用 write_files 一次提交多个文件"，AI 会先输出 1-3 行计划再批量改。

**Q: 服务器部署后端怎么对外暴露**
A: 后端 `--host 0.0.0.0` 已能从局域网访问。生产建议：
- nginx 反向代理 + HTTPS
- CORS 改成具体 origin（`.env` 的 `CORS_ORIGINS=https://your-frontend.com`）
- Tauri 客户端打包后内置后端配置

**Q: 凭据丢了怎么办**
A: 浏览器右上角【凭据】按钮重填。或者在浏览器开发者工具里清掉 localStorage 的 `app-for-oneself-creds`，刷新页面会自动弹引导框。

**Q: 想用 Claude / Kimi / 通义千问 而不是 DeepSeek**
A: 当前只接了 DeepSeek。其他 provider 实现起来 30 行代码，参考 [扩展开发 → 新增 AI provider](#新增-ai-provider)。

**Q: 端口冲突**
A: `--port` 改成空闲端口，记得同步改 `frontend/vite.config.js` 里的 `proxy.target`。

**Q: 国内访问 GitHub API 慢**
A: 给 Python httpx 设置代理：

```bash
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890
```

或者在 `.env` 后续加 `GITHUB_API_BASE=https://your-mirror/api`（自建 Cloudflare Worker 反代，M2 内置）。

---

## 安全提醒

- 当前 M1 版本：凭据**明文存浏览器 localStorage**，没加密。XSS 风险存在。
- `.env` 后端凭据是开发兜底，**不要把 `.env` 推到 GitHub**（已在 .gitignore）。
- GitHub PAT 建议用 fine-grained 而不是 classic，且**只勾选必需的仓库**。
- 测试过程中用过的 PAT / API key 如果在聊天工具里发过，**务必撤销重生成**。
- M2 会加：WebCrypto 加密保险箱 + 口令解锁 + Tauri 桌面端安全存储。

---

## License

MIT
