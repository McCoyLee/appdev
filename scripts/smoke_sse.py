"""测试 /api/chat SSE 端点。"""

from __future__ import annotations

import asyncio
import json
import time

import httpx

URL = "http://127.0.0.1:8901/api/chat"


async def main() -> None:
    ts = int(time.time())
    payload = {
        "messages": [
            {
                "role": "user",
                "content": (
                    f"在仓库根目录新建 sse-test-{ts}.md，写一行 'sse pipe ok'。"
                    f"分支用 ai/sse-{ts}，提交并开 PR。"
                ),
            }
        ],
        "max_iterations": 8,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0), trust_env=False) as client:
        async with client.stream("POST", URL, json=payload) as resp:
            print(f"HTTP {resp.status_code} | content-type={resp.headers.get('content-type')}")
            event_type = None
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    raw = line[5:].strip()
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        data = raw
                    if event_type == "assistant_text":
                        txt = data.get("content", "") if isinstance(data, dict) else ""
                        if txt.strip():
                            print(f"\n💬 {txt[:200]}{'...' if len(txt) > 200 else ''}")
                    elif event_type == "tool_call":
                        print(f"🔧 {data['name']}({list(data['arguments'].keys())})")
                    elif event_type == "tool_result":
                        p = data["payload"]
                        if p.get("ok"):
                            print(f"   → OK: {str(p.get('result'))[:80]}")
                        else:
                            print(f"   → ERR: {p.get('error')}")
                    elif event_type == "usage":
                        print(f"\n📊 {data}")
                    elif event_type == "done":
                        print(f"✅ done: {data}")
                    elif event_type == "error":
                        print(f"❌ {data}")


if __name__ == "__main__":
    asyncio.run(main())
