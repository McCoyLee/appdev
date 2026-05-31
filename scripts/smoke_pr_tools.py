"""
M4-4 验证 AI agent 的 PR 协作工具（list_prs / comment_pr / merge_pr）
直接打 tools.dispatch（不经过 LLM，确定性强）。

用法（项目根目录）：
    conda run -n appdev python scripts/smoke_pr_tools.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.ai.tools import dispatch  # noqa: E402
from backend.app.core.config import get_settings  # noqa: E402
from backend.app.github.client import GitHubClient  # noqa: E402


async def main() -> None:
    s = get_settings()
    repo = s.test_repo
    ts = int(time.time())
    branch = f"ai/smoke-prtool-{ts}"
    fname = f"smoke-prtool-{ts}.md"

    print(f"== repo: {repo} branch: {branch}\n")

    async with GitHubClient(s.github_token) as gh:
        base = (await gh.get_repo(repo))["default_branch"]
        await gh.ensure_branch(repo, branch, from_ref=base)
        await gh.write_files(
            repo, branch,
            files=[{"path": fname, "content": f"# prtool {ts}\n"}],
            message=f"smoke: {fname}",
        )

        # open_pr（agent 工具）
        r = await dispatch(gh, repo, "open_pr", {"title": f"prtool {ts}", "head": branch, "base": base})
        assert r["ok"], r
        num = r["result"]["number"]
        print(f"1) open_pr → #{num}")

        # list_prs（agent 工具）
        r = await dispatch(gh, repo, "list_prs", {"state": "open"})
        assert r["ok"] and any(p["number"] == num for p in r["result"]), r
        print(f"2) list_prs → {len(r['result'])} open, 含 #{num} ✓")

        # comment_pr（agent 工具）
        r = await dispatch(gh, repo, "comment_pr", {"number": num, "body": "agent 工具自动留言 🤖"})
        assert r["ok"], r
        print("3) comment_pr ✓")

        # 错误参数被优雅捕获
        r = await dispatch(gh, repo, "merge_pr", {"number": num, "method": "bogus"})
        assert not r["ok"] and "bad arguments" in r["error"], r
        print("4) merge_pr 非法 method 被拦 ✓")

        # merge_pr（agent 工具）
        r = await dispatch(gh, repo, "merge_pr", {"number": num})
        assert r["ok"] and r["result"]["merged"], r
        print(f"5) merge_pr → merged, branch_deleted={r['result']['branch_deleted']} ✓")

        # 兜底清分支
        try:
            await gh.delete_branch(repo, branch)
        except Exception:
            pass

        print("\n✅ smoke_pr_tools PASS")


if __name__ == "__main__":
    asyncio.run(main())
