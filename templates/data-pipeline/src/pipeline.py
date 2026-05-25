"""数据流水线：抓取 → 处理 → 输出。

定时（cron）跑，结果写到 data/ 目录并 commit 回仓库（也可改成 upload artifact）。
改 fetch() / transform() 实现你的业务。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch() -> list[dict]:
    """抓数据。示例：拉一个公开 API。AI 通常改这里。"""
    resp = httpx.get("https://api.github.com/repos/python/cpython", timeout=20)
    resp.raise_for_status()
    d = resp.json()
    return [{"name": d["full_name"], "stars": d["stargazers_count"]}]


def transform(rows: list[dict]) -> dict:
    """处理数据。AI 通常改这里。"""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "items": rows,
    }


def save(result: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "latest.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run() -> dict:
    rows = fetch()
    result = transform(rows)
    path = save(result)
    print(f"OK: wrote {path} ({result['count']} items)")
    return result


if __name__ == "__main__":
    run()
