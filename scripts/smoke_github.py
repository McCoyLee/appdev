"""
M0-2 烟雾测试：对真实仓库跑一遍 GitHub 封装层的所有核心方法。
运行：conda run -n appdev python scripts/smoke_github.py
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


async def _step(label: str, coro):
    try:
        result = await coro
        print(f"✓ {label}")
        return result, None
    except GitHubError as e:
        print(f"✗ {label} | {e}")
        return None, e


async def main() -> None:
    s = get_settings()
    if not s.github_token or not s.test_repo:
        print("missing GITHUB_TOKEN or TEST_REPO in .env")
        sys.exit(1)

    repo = s.test_repo
    branch = f"smoke/m0-2-{int(time.time())}"
    print(f"== repo: {repo} | smoke branch: {branch}")

    async with GitHubClient(s.github_token) as gh:
        # 1. whoami
        me = await gh.whoami()
        print(f"1. whoami: {me['login']}")

        # 2. repo info
        info = await gh.get_repo(repo)
        default_branch = info["default_branch"]
        print(f"2. repo: {info['full_name']} | default={default_branch} | private={info['private']}")

        # 3. list root
        entries = await gh.list_dir(repo)
        print(f"3. list_dir(/): {len(entries)} entries -> {[e['name'] for e in entries[:5]]}")

        # 4. create branch
        sha = await gh.ensure_branch(repo, branch, default_branch)
        print(f"4. ensure_branch({branch}) sha={sha[:7]}")

        # 5. write file (new)
        path = "smoke/hello.md"
        commit = await gh.write_file(
            repo,
            path,
            content=f"# hello from M0-2\nbranch={branch}\nts={time.time()}\n",
            message=f"smoke: create {path}",
            branch=branch,
        )
        new_sha = commit["content"]["sha"]
        print(f"5. write_file({path}) sha={new_sha[:7]}")

        # 6. read file back
        got = await gh.read_file(repo, path, ref=branch)
        print(f"6. read_file({path}): {len(got['content'])} bytes, first line='{got['content'].splitlines()[0]}'")

        # 7. update file
        commit2 = await gh.write_file(
            repo,
            path,
            content=got["content"] + "\nupdated!\n",
            message=f"smoke: update {path}",
            branch=branch,
            sha=got["sha"],
        )
        print(f"7. write_file(update) sha={commit2['content']['sha'][:7]}")

        # 8. PR
        pr = await gh.open_pr(
            repo,
            title=f"[smoke] {branch}",
            head=branch,
            base=default_branch,
            body="auto smoke test, safe to close",
        )
        print(f"8. open_pr: #{pr['number']} {pr['html_url']}")

        # 9. secrets
        secret_name = "SMOKE_SECRET"
        _, err = await _step(
            f"9.  set_secret({secret_name})",
            gh.set_secret(repo, secret_name, "shhhh"),
        )
        if not err:
            secrets, _ = await _step("    list_secrets", gh.list_secrets(repo))
            if secrets is not None:
                print(f"    total secrets: {len(secrets)} | names={[s['name'] for s in secrets]}")
            await _step("    delete_secret", gh.delete_secret(repo, secret_name))

        # 10. variables（独立权限，可能未授权）
        var_name = "SMOKE_VAR"
        _, err = await _step(
            f"10. set_variable({var_name})",
            gh.set_variable(repo, var_name, f"hello-{int(time.time())}"),
        )
        if not err:
            vars_, _ = await _step("    list_variables", gh.list_variables(repo))
            if vars_ is not None:
                print(f"    total vars: {len(vars_)}")
            await _step("    delete_variable", gh.delete_variable(repo, var_name))

        # 11. workflows
        wfs, _ = await _step("11. list_workflows", gh.list_workflows(repo))
        if wfs is not None:
            print(f"    {len(wfs)} workflows -> {[w['name'] for w in wfs]}")

        # 12. cleanup
        await _step(f"12. close_pr(#{pr['number']})", gh.close_pr(repo, pr["number"]))
        await _step(f"    delete_branch({branch})", gh.delete_branch(repo, branch))

    print("\nALL OK")


if __name__ == "__main__":
    asyncio.run(main())
