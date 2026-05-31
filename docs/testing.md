# 测试验收手册

分四层：A 自动化烟雾 → B 后端 API → C 浏览器手动 → D 桌面端。

---

## A. 自动化烟雾测试（命令行，最快）

```bash
cd /home/limaocheng/app-for-oneself

# 1. GitHub 封装层（读写/分支/PR/secrets/workflows 12 步，自清理）
conda run -n appdev python scripts/smoke_github.py    # 结尾 ALL OK

# 2. AI agent 端到端（DeepSeek 真改文件 + 开分支 + 自清理）
conda run -n appdev python scripts/smoke_agent.py     # 结尾 ✅ done

# 3. SSE 流式对话（需后端在 8901 跑）
conda run -n appdev python scripts/smoke_sse.py

# 4. PR 协作工作流（建分支→开 PR→列表→详情→评论→合并→清理，自清理）
conda run -n appdev python scripts/smoke_pr.py        # 结尾 ✅ smoke_pr PASS

# 5. AI agent 的 PR 协作工具（list/comment/read_feedback/merge，直打 dispatch 不经 LLM）
conda run -n appdev python scripts/smoke_pr_tools.py  # 结尾 ✅ smoke_pr_tools PASS

# 6. 离线单元测试（纯函数，无网络，秒级）—— prs.py 的 CI 汇总/patch 截断/PR 摘要
conda run -n appdev python -m pytest tests/ -q        # 结尾 N passed
```

通过标志：smoke 步骤带 ✓ / 结尾 `ALL OK` / `✅ done`；pytest 结尾 `passed`。
1~3 过说明「GitHub API + AI agent + SSE」核心链路完好；4~6 覆盖 M4 PR 协作。

---

## B. 后端 API 逐个验（curl）

```bash
cd /home/limaocheng/app-for-oneself
set -a; source .env; set +a
B=http://127.0.0.1:8901

curl -s $B/healthz | python -m json.tool
curl -s $B/api/templates | python -c "import sys,json;print([t['id'] for t in json.load(sys.stdin)['templates']])"   # 6 个
curl -s -H "X-GitHub-Token: $GITHUB_TOKEN" $B/api/probe/github
curl -s -X POST -H "X-AI-Key: $DEEPSEEK_API_KEY" -H "X-AI-Provider: deepseek" $B/api/probe/ai
curl -s "$B/api/branches"
curl -s "$B/api/preview?branch=main" | python -m json.tool
```

完整端点表见 `README.md` 的「API 端点速查」。

---

## C. 浏览器手动验收

访问 `http://<服务器IP>:5173`（同局域网）或 SSH 端口转发后 `http://localhost:5173`。

### 重要：如何重现「首次启动引导」

如果你之前用过、`localStorage` 里有凭据，App 会直接进工作台、跳过引导。重现方法：

- **清凭据**（F12 Console）：`localStorage.removeItem('app-for-oneself-creds'); location.reload()` —— 清前先复制好 token
- **无痕窗口**：开隐私窗口访问，干净环境走完整引导
- **不清也能测**：点顶栏右上【凭据】按钮，对话框就是引导核心

### 验收清单

| # | 功能（里程碑） | 操作 | 期望 |
|---|---|---|---|
| 1 | 启动引导 (M2-4) | 清 localStorage 后刷新 | 自动弹凭据对话框 |
| 2 | 凭据测试 (M2-4) | 凭据框填 token → 点【测试】 | ✓ + 用户名；仓库下拉自动列出 |
| 3 | 凭据加密 (M3-1) | 勾「启用主密码加密」→ 设密码 → 保存 → 刷新 | 弹解锁框，密码对才进；顶栏 🔐已加密 |
| 4 | 聊天改代码 (M0) | 输「把首页标题改成 XXX」 | tool 卡片实时流：read→branch→write→run_ci |
| 5 | CI 闭环 (M1-3) | 看上一步 | run_ci 卡片，CI success（失败会看到 AI 自修复）|
| 6 | 预览 (M1-1/2) | 右栏「预览」tab | iframe 显示部署内容* |
| 7 | 一键采纳 (M1-2) | 预览面板【就这版】 | merge 到 main，分支清掉，顶栏分支徽章消失 |
| 8 | 计划模式 (M2-7) | 输「大改：加导航栏+关于页+联系页」 | PlanCard checklist，可勾选→【按此执行】|
| 9 | 项目索引 (M2-5) | 输「看看项目结构」 | AI 调 get_project_outline 一次列全图 |
| 10 | 新建项目 (M2-2) | 顶栏【+新建项目】 | 3 步向导，6 个模板可选 |
| 11 | 多仓库 (M2-3) | 顶栏仓库名 dropdown | 切换历史仓库 |
| 12 | 日志流 (M2-8) | 「运行」tab →【看日志】 | 暗色终端，日志（历史/实时）|
| 13 | 密码本 (M1) | 「密码本」tab → 添加 | secret 加/删 |

\* 第 6/7 需先一次性配置：仓库 Settings → Pages → Source = **GitHub Actions**；
   首次 ai/* 部署失败时点预览面板的【一键放开限制】（或手动 Settings → Environments → github-pages → Deployment branches → No restriction）。

---

## D. 桌面端（Tauri，仅本地桌面机）

本服务器无法编译（无 Rust + webkit2gtk + 无头）。在你的 Mac/Windows：

```bash
cd src-tauri
npx @tauri-apps/cli icon path/to/logo.png   # 先生成图标（必须，否则报错）
npm install
npm run dev                                   # 编译 + 自动起后端 + 开窗口
```

详见 [desktop.md](./desktop.md)。报错贴输出。

---

## 排错速查

| 现象 | 原因 / 解法 |
|---|---|
| 前端转圈进不去 | 后端没起 / 凭据无效；点【凭据】重填 |
| 401 | token 缺失或无效 |
| 403 on Pages | 分支策略限制，点【一键放开限制】或加 PAT Environments 权限 |
| 403 on 新建项目 | PAT 缺 Repository creation 权限，改用「已有仓库」模式 |
| CI 一直 queued | GitHub Actions 排队；等或看 GitHub 网页 |
| 预览 iframe 空白 | Pages 没启用，或部署还没跑完 |
| `conda run` 报 No module named 'backend' | 没在项目根目录跑 |
