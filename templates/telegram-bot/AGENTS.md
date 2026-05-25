# AGENTS.md

## 项目类型

**Telegram 机器人**。python-telegram-bot v21，本地 polling 调试 / 线上 webhook（部署到 Render）。

## 文件结构

- `bot.py` — 入口。`start` / `echo` 是示例 handler，**业务逻辑改这里**。
- `requirements.txt` — 依赖
- `.github/workflows/ci.yml` — ruff + 可构建性检查
- `.github/workflows/deploy.yml` — push main 后触发 Render 部署

## 必需 secrets

- `TELEGRAM_BOT_TOKEN` — 找 @BotFather 创建机器人拿到
- `WEBHOOK_URL` — 线上 webhook 模式用，Render 服务的公开地址（变量也行）
- `RENDER_DEPLOY_HOOK` — 部署用

## 修改约定

1. 新增命令用 `CommandHandler`，文本处理用 `MessageHandler`，都在 `build_app()` 里注册
2. 不要把 token 写死在代码里，永远从 `os.environ` 读
3. `build_app()` 必须保持可被 CI 无 token 构建（CI 用 dummy token 只测构建）
4. 加依赖同步更新 `requirements.txt`
5. 改完调 `run_ci`
