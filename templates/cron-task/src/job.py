"""定时任务入口。改写 do_job() 实现你的业务。"""

from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from datetime import datetime


def do_job() -> str:
    """返回要发送的内容（字符串）。AI 通常会改这里。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"定时任务跑了一次，时间：{now}\n\n这里写你的业务结果。"


def send_mail(subject: str, body: str) -> None:
    user = os.environ["SMTP_USER"]
    pw = os.environ["SMTP_PASS"]
    to_addr = os.environ.get("MAIL_TO", user)
    host = os.environ.get("SMTP_HOST", "smtp.qq.com")
    port = int(os.environ.get("SMTP_PORT", "465"))

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP_SSL(host, port, timeout=30) as s:
        s.login(user, pw)
        s.send_message(msg)


def main() -> int:
    try:
        body = do_job()
        subject = os.environ.get("MAIL_SUBJECT", "定时任务结果")
        send_mail(subject, body)
        print("OK: mail sent")
        return 0
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
