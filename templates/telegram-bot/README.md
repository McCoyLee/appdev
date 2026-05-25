# 我的 Telegram 机器人

## 怎么用

1. 找 [@BotFather](https://t.me/BotFather) 发 `/newbot` 创建机器人，拿到 token
2. 在客户端密码本添加 `TELEGRAM_BOT_TOKEN`
3. 对 AI 说想让机器人做什么，比如：
   - "加一个 /weather 命令，查天气"
   - "用户发图片时存到某处"
   - "做一个每日提醒功能"
4. 本地调试：`BOT_MODE=polling python bot.py`
5. 上线：部署到 Render（webhook 模式），配 `WEBHOOK_URL` + `RENDER_DEPLOY_HOOK`
