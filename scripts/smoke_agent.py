"""
M0-3 端到端：让 DeepSeek 真的在测试仓库里改一个文件并开 PR。
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ai.agent import Agent  # noqa: E402
from backend.app.ai.providers.deepseek import DeepSeekProvider  # noqa: E402
from backend.app.core.config import get_settings  # noqa: E402
from backend.app.github.client import GitHubClient  # noqa: E402


USER_TASK = (
    "请在仓库根目录新建一个 hello-from-ai.md，内容是欢迎语 + 当前时间戳。"
    "新分支名用 ai/hello-{时间戳}，然后提交并开 PR。"
)


async def main() -> None:
    s = get_settings()
    ts = int(time.time())

    provider = DeepSeekProvider(
        api_key=s.deepseek_api_key,
        base_url=s.deepseek_base_url,
        model=s.deepseek_model,
    )

    history = [
        {"role": "user", "content": USER_TASK.replace("{时间戳}", str(ts))},
    ]

    print(f"== repo: {s.test_repo}")
    print(f"== task: {history[0]['content']}\n")

    pr_url: str | None = None
    branch_name: str | None = None

    async with GitHubClient(s.github_token) as gh:
        agent = Agent(provider, gh, s.test_repo, max_iterations=10)
        async for ev in agent.run(history):
            if ev.type == "assistant_text":
                txt = ev.data["content"].strip()
                if txt:
                    print(f"\n💬 assistant:\n{txt}\n")
            elif ev.type == "tool_call":
                args_preview = {
                    k: (v[:60] + "...") if isinstance(v, str) and len(v) > 60 else v
                    for k, v in ev.data["arguments"].items()
                }
                print(f"🔧 tool_call {ev.data['name']}({args_preview})")
                if ev.data["name"] == "ensure_branch":
                    branch_name = ev.data["arguments"].get("branch")
            elif ev.type == "tool_result":
                payload = ev.data["payload"]
                ok = payload.get("ok")
                if ok:
                    result = payload.get("result")
                    if isinstance(result, dict) and "html_url" in result:
                        pr_url = result["html_url"]
                    summary = str(result)[:120]
                else:
                    summary = f"ERROR: {payload.get('error')}"
                print(f"   → {summary}")
            elif ev.type == "usage":
                print(f"\n📊 usage: {ev.data}")
            elif ev.type == "done":
                print(f"\n✅ done: {ev.data}")
            elif ev.type == "error":
                print(f"\n❌ error: {ev.data}")

    await provider.aclose()

    # 清理：关 PR + 删分支（避免重复测试堆 PR）
    if pr_url:
        print(f"\nPR created: {pr_url}")
    if branch_name:
        async with GitHubClient(s.github_token) as gh:
            # 找最新一个开着的 ai/* PR
            prs = await gh._request(
                "GET", f"/repos/{s.test_repo}/pulls", params={"state": "open", "head": f"{s.test_repo.split('/')[0]}:{branch_name}"}
            )
            for pr in prs or []:
                await gh.close_pr(s.test_repo, pr["number"])
                print(f"cleanup: closed PR #{pr['number']}")
            try:
                await gh.delete_branch(s.test_repo, branch_name)
                print(f"cleanup: deleted branch {branch_name}")
            except Exception as e:
                print(f"cleanup branch failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
