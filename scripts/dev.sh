#!/usr/bin/env bash
# 一键启动开发环境：后端 (uvicorn) + 前端 (vite)。
# Tauri 桌面端开发用 `cd src-tauri && npm run dev`（它会自己拉起后端）。

set -e
cd "$(dirname "$0")/.."

echo "==> 启动后端 (127.0.0.1:8901)"
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8901 --reload &
BACKEND_PID=$!

cleanup() {
  echo "==> 停止后端 pid=$BACKEND_PID"
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> 启动前端 (5173)"
cd frontend
npm run dev -- --host 0.0.0.0
