# AGENTS.md

## 项目类型

**定时任务 + 邮件通知**。Python 3.11，GitHub Actions cron 触发，跑完发邮件。

## 文件结构

- `src/job.py` — 任务入口。**改 `do_job()` 函数**实现业务，它返回要发送的字符串。
- `tests/test_job.py` — 基础测试
- `requirements.txt` — Python 依赖
- `.github/workflows/ci.yml` — 跑 pytest + 入口可执行检查
- `.github/workflows/cron.yml` — 定时（默认每天北京 7:00）跑 `src.job`

## 必需的 secrets（用户在前端密码本添加）

- `SMTP_USER` — 邮箱地址，如 `xxx@qq.com`
- `SMTP_PASS` — 邮箱 SMTP 授权码（不是登录密码）
- `MAIL_TO` — 收件人，可选，默认发给自己

## 修改约定

1. 业务逻辑只改 `src/job.py` 的 `do_job()`，**别动 `send_mail` 和 `main`**
2. 加新依赖同步更新 `requirements.txt`
3. 改 cron 时间：`cron.yml` 里的 `cron: "0 23 * * *"`（**UTC 时区**，北京时间 +8h）
4. 修改完调 `run_ci`
