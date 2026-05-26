# 开发路线图

已完成 M0~M3（详见 [进度.md](../进度.md)）。本文件是**未来开发计划**，按可执行任务拆解，供接力开发直接 pick up。

## 已完成回顾

| 里程碑 | 主题 | 状态 |
|---|---|---|
| M0 | 骨架 + GitHub 封装 + AI agent + SSE + 静态站 e2e | ✅ |
| M1 | preview-first 工作流 + CI 闭环 + 一键采纳 + 多模板 + 多用户凭据 | ✅ |
| M2 | 新建项目向导 + 多仓库 + 项目索引 + 计划模式 + 日志流 | ✅ |
| M3 | 凭据加密 + 自动 rebase + 模板扩到 6 个 + Tauri 骨架 | ✅ |

---

## M4 候选（未开始）

下面 5 个方向，**优先级从高到低**。每个标了涉及文件 + 验收标准。建议一次选 1-2 个主题做，沿用「每步追加进度.md + 中文 commit」习惯。

### M4-A 桌面端真跑通「双击即用」（最高价值）

把 Tauri 桌面端从「代码就位」变成「能编译能运行」。**必须在有图形界面的开发机做**（Mac/Win/Linux 桌面，非本服务器）。

- **A1** 本地装 Rust + 平台依赖（见 docs/desktop.md），`cd src-tauri && npm install && npm run dev` 跑通，修编译错误
  - 涉及：`src-tauri/src/lib.rs`、`tauri.conf.json`
  - 验收：双击窗口打开，自动起后端，前端连上 8901
- **A2** PyInstaller 把 Python 后端冻结成单二进制 sidecar
  - 涉及：新增 `scripts/build_backend.py` 或 spec 文件；`lib.rs` 改用 `tauri_plugin_shell` sidecar API
  - 注意：PyNaCl 要 `--collect-all nacl`；产物 ~80MB
  - 验收：用户机器**无需装 Python** 也能跑
- **A3** 凭据改用 OS keychain（Tauri `tauri-plugin-stronghold` 或系统 keyring）替代 localStorage
  - 验收：凭据存系统安全区，比浏览器 localStorage 更安全
- **A4** 打包签名：macOS notarize、Windows 证书（需账号，可后置）

### M4-B 多人协作

- **B1** PR 列表面板：列 open PRs，UI 看 diff
  - 涉及：`backend/app/api/` 新增 pulls 端点；前端新 PullsPanel.vue
- **B2** PR 评论 / issue agent：让 AI 处理 issue（"帮我看看 #42"）
  - 涉及：`tools.py` 加 query_issues / add_comment 工具（client.py 已有部分）
- **B3** collaborator 管理：UI 邀请队友进仓库

### M4-C 移动端 / PWA

- **C1** 响应式布局：Workspace 左右分栏在窄屏改上下 tab
  - 涉及：`views/Workspace.vue`、各 Panel 的 CSS
- **C2** PWA：加 manifest + service worker，手机能「添加到主屏」
  - 涉及：`frontend/` 加 vite-plugin-pwa

### M4-D 多用户 SaaS 化

把单用户工具变成多人在线服务。

- **D1** 用户会话隔离：后端按请求凭据隔离，加简单 session/JWT
- **D2** 用量统计 + 配额：记录每用户 token 消耗，超额提示
- **D3** 计费集成（如需要）
- **D4** 部署：Docker 化后端 + 前端 CDN + HTTPS + CORS 收紧
  - 涉及：新增 `Dockerfile`、`docker-compose.yml`、nginx 配置

### M4-E 国内体验优化

- **E1** GitHub API 加速反代：内置 Cloudflare Worker 配置，`GITHUB_API_BASE` 可切镜像
- **E2** Pages 国内访问：自动同步到 Gitee Pages 或 Cloudflare Pages
- **E3** 首次安装网络体检页

---

## 工程债（穿插着还）

- [ ] 前端 bundle 1.2MB 未做 code split（vite manualChunks）
- [ ] DeepSeek prompt caching 命中率无观测（usage 没透出 cache 字段）
- [ ] squash-rebase 丢中间 commit（可选实现真 cherry-pick rebase 保留历史）
- [ ] 后端无单元测试（只有 smoke 脚本）；可加 pytest + httpx mock
- [ ] Variables 权限探测：token 检查时分别标注 secrets/variables 是否授权
- [ ] agent loop 超长对话未做上下文压缩

---

## 接力提示

- 新会话先读 [CLAUDE.md](../CLAUDE.md) 拿全局，再看本文件挑任务
- 启动开发环境：`bash scripts/dev.sh`（或分别起后端 8901 + 前端 5173）
- 测试：`docs/testing.md`
- 改完推送：commit 中文 + `Co-Authored-By: Claude`，push 到 `McCoyLee/appdev`
