"""
把指定模板推到测试仓库的 main 分支。

用法：
  python scripts/init_template.py                # 默认 static-site
  python scripts/init_template.py api-server     # 切换到 api-server
  python scripts/init_template.py cron-task

注意：这会**覆盖**仓库现有内容（在 main 上 commit）。
M2 后会改成"创建新仓库"工作流。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.core.config import get_settings  # noqa: E402
from backend.app.github.client import GitHubClient  # noqa: E402
from backend.app.github.errors import GitHubNotFound  # noqa: E402

TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"


async def main() -> None:
    template_id = sys.argv[1] if len(sys.argv) > 1 else "static-site"
    template_dir = TEMPLATES_ROOT / template_id
    if not template_dir.is_dir():
        avail = [d.name for d in TEMPLATES_ROOT.iterdir() if d.is_dir()]
        print(f"模板 {template_id} 不存在；可用：{avail}")
        sys.exit(1)

    s = get_settings()
    if not s.test_repo:
        print("missing TEST_REPO in .env")
        sys.exit(1)

    # 排除 template.json（仅本仓库内部使用，不推到目标仓库）
    files: list[tuple[str, str]] = []
    for p in template_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(template_dir).as_posix()
        if rel == "template.json":
            continue
        files.append((rel, p.read_text(encoding="utf-8")))

    print(f"== pushing template '{template_id}' ({len(files)} files) → {s.test_repo}@main")

    async with GitHubClient(s.github_token) as gh:
        info = await gh.get_repo(s.test_repo)
        branch = info["default_branch"]

        for path, content in files:
            try:
                existing = await gh.read_file(s.test_repo, path, ref=branch)
                sha = existing.get("sha")
                if existing.get("content") == content:
                    print(f"   skip   {path}")
                    continue
            except GitHubNotFound:
                sha = None

            await gh.write_file(
                s.test_repo,
                path=path,
                content=content,
                message=f"[{template_id}] {'init' if not sha else 'update'} {path}",
                branch=branch,
                sha=sha,
            )
            print(f"   {'update' if sha else 'create'} {path}")

    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
