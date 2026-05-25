"""一个 Flask web 应用起手项目。AI 可扩展路由、模板、数据库。"""

from __future__ import annotations

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

INDEX_HTML = """
<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>我的 Flask 应用</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 48px auto; text-align: center">
  <h1>🌶️ Flask 应用已就绪</h1>
  <p>跟 AI 说你想加什么功能。</p>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(INDEX_HTML)


@app.get("/api/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
