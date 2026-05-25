# 我的 Flask 应用

## 本地跑

```bash
pip install -r requirements.txt
python app.py   # http://127.0.0.1:8000
```

## 怎么用 AI 扩展

跟 AI 说：
- "加一个留言板，留言存 SQLite"
- "加用户登录"
- "做一个图片上传 + 展示页"

AI 改代码 → 加测试 → 跑 CI → 你点「就这版」→ Render 自动部署。

## 部署

去 [render.com](https://render.com) 建 Web Service，Build `pip install -r requirements.txt`，
Start `gunicorn app:app`，把 Deploy Hook 放到仓库 secrets 的 `RENDER_DEPLOY_HOOK`。
