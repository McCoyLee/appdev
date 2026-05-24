# 我的 API

FastAPI 起手项目。

## 本地跑（可选）

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000/docs
```

## 怎么用 AI 扩展

在 App For Oneself 客户端里跟 AI 说：
- "加一个 /todos 接口，能增删查改待办"
- "用 SQLite 存数据"
- "加 JWT 登录"

AI 会：
1. 在 `ai/*` 分支上改代码
2. 自动加测试
3. 自动跑 CI 确认没问题
4. 你点"就这版"采纳到 main，Render 自动部署
