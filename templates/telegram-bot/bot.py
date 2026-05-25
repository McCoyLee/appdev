"""一个 Telegram 机器人起手项目（webhook 模式，部署到 Render）。

改 handlers 实现你的业务。本地用 polling 调试，线上用 webhook。
"""

from __future__ import annotations

import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("你好！我是你的机器人，发点什么试试。")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """默认回声；AI 通常改这里实现业务。"""
    await update.message.reply_text(f"你说：{update.message.text}")


def build_app() -> Application:
    if not TOKEN:
        raise RuntimeError("缺少 TELEGRAM_BOT_TOKEN 环境变量")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    return app


def main() -> None:
    app = build_app()
    mode = os.environ.get("BOT_MODE", "polling")
    if mode == "webhook":
        # 线上：Render 提供 PORT，用 webhook
        port = int(os.environ.get("PORT", "8080"))
        url = os.environ["WEBHOOK_URL"]  # 形如 https://xxx.onrender.com
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TOKEN,
            webhook_url=f"{url}/{TOKEN}",
        )
    else:
        # 本地调试：polling
        app.run_polling()


if __name__ == "__main__":
    main()
