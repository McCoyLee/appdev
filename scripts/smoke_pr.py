"""
M4 PR 协作工作流烟雾测试：在测试仓库里真实跑一遍
建分支 → 改文件 → 开 PR → 列表 → 详情(文件/CI/评论) → 留言 → 合并 → 验证分支清理。

用法（项目根目录）：
    conda run -n appdev python scripts/smoke_pr.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.core.config import get_settings  # noqa: E402
from backend.app.github.client import GitHubClient  # noqa: E402
from backend.app.github.errors import GitHubError  # noqa: E402


async def main() -> None:
    s = get_settings()
    repo = s.test_repo
    ts = int(time.time())
    branch = f"ai/smoke-pr-{ts}"
    fname = f"smoke-pr-{ts}.md"

    print(f"== repo: {repo}")
    print(f"== branch: {branch}\n")

    async with GitHubClient(s.github_token) as gh:
        # 默认分支
        info = await gh.get_repo(repo)
        base = info["default_branch"]
        print(f"1) default branch = {base}")

        # 建分支 + 写文件
        await gh.ensure_branch(repo, branch, from_ref=base)
        await gh.write_files(
            repo, branch,
            files=[{"path": fname, "content": f"# smoke pr {ts}\n\nhello from M4 PR test\n"}],
            message=f"smoke: add {fname}",
        )
        print(f"2) branch + file pushed: {fname}")

        # 开 PR
        pr = await gh.open_pr(repo, title=f"smoke PR {ts}", head=branch, base=base, body="自动化测试 PR")
        num = pr["number"]
        print(f"3) PR opened: #{num} {pr['html_url']}")

        # 列表（应包含本 PR）
        prs = await gh.list_prs(repo, state="open")
        assert any(p["number"] == num for p in prs), "新开的 PR 没出现在列表里"
        print(f"4) list_prs ok ({len(prs)} open)")

        # 详情 + 文件 + 状态
        detail = await gh.get_pr(repo, num)
        files = await gh.list_pr_files(repo, num)
        head_sha = detail["head"]["sha"]
        combined = await gh.get_combined_status(repo, head_sha)
        checks = await gh.list_check_runs(repo, head_sha)
        assert any(f["filename"] == fname for f in files), "PR 文件列表不含改动文件"
        print(f"5) detail ok: {len(files)} file(s), status={combined.get('state')}, {len(checks)} check-run(s)")

        # 评论（PR 级讨论）
        c = await gh.create_pr_comment(repo, num, "smoke 自动留言 👋")
        comments = await gh.list_pr_comments(repo, num)
        assert any("smoke 自动留言" in x["body"] for x in comments), "评论没写进去"
        print(f"6) comment ok ({len(comments)} comment(s))")

        # 行内评论（绑定文件 + 行）
        await gh.create_review_comment(
            repo, num, "行内：这行是标题 ✅", commit_id=head_sha, path=fname, line=1
        )
        rcs = await gh.list_review_comments(repo, num)
        assert any(x.get("path") == fname for x in rcs), "行内评论没写进去"
        print(f"6b) review_comment ok (file={fname} line=1, {len(rcs)} 条)")

        # 合并（squash），失败则关闭兜底
        merged = False
        try:
            res = await gh.merge_pr(repo, num, method="squash")
            merged = res.get("merged", False)
            print(f"7) merged: sha={res.get('sha')}")
        except GitHubError as e:
            print(f"7) merge blocked ({e.status} {e.message}) → 关闭 PR 兜底")
            await gh.close_pr(repo, num)

        # 清理分支
        try:
            await gh.delete_branch(repo, branch)
            print("8) branch cleaned")
        except GitHubError as e:
            print(f"8) branch cleanup skipped: {e.message}")

        print(f"\n✅ smoke_pr PASS (merged={merged})")


if __name__ == "__main__":
    asyncio.run(main())
