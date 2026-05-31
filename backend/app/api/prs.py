"""Pull Request 协作工作流（M4）。

把「采纳 AI 分支」从「直接 FF 进 main」升级成可选的 PR 流程：
- AI 改完代码留在 ai/* 分支 → 用户可以「提个 PR 让别人 review」
- 列出 open/closed PR，看每个 PR 的 CI 状态 + 改了哪些文件
- 在 PR 上留言讨论（多人协作）
- review 满意后一键 merge（默认 squash），可顺带删分支 + 刷新预览

设计上与 branches.py 的「就这版」并存：
- 想快就直接 adopt（FF 进 main）
- 想协作/留痕就走 PR
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from ..github.client import GitHubClient
from ..github.errors import GitHubError, GitHubNotFound
from .deps import github_client, require_repo

router = APIRouter(prefix="/api/prs", tags=["prs"])

PAGES_WORKFLOW = "pages.yml"


def _summarize_pr(pr: dict) -> dict:
    return {
        "number": pr["number"],
        "title": pr["title"],
        "state": pr["state"],
        "draft": pr.get("draft", False),
        "merged": pr.get("merged", False),
        "head": pr["head"]["ref"],
        "head_sha": pr["head"]["sha"],
        "base": pr["base"]["ref"],
        "user": pr["user"]["login"] if pr.get("user") else None,
        "html_url": pr["html_url"],
        "comments": pr.get("comments"),
        "mergeable": pr.get("mergeable"),
        "mergeable_state": pr.get("mergeable_state"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "changed_files": pr.get("changed_files"),
        "created_at": pr["created_at"],
        "updated_at": pr["updated_at"],
    }


@router.get("")
async def list_prs(
    state: str = Query("open", description="open|closed|all"),
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """列出仓库的 PR（默认只看 open，按更新时间倒序）。"""
    if state not in ("open", "closed", "all"):
        raise HTTPException(400, "state 只能是 open / closed / all")
    try:
        prs = await gh.list_prs(repo, state=state)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {"prs": [_summarize_pr(p) for p in prs]}


def _checks_summary(combined: dict, check_runs: list[dict]) -> dict:
    """把 legacy status + check runs 揉成一个好懂的状态。"""
    items: list[dict] = []
    for s in combined.get("statuses", []):
        items.append(
            {
                "name": s.get("context", "status"),
                "status": "completed",
                "conclusion": s.get("state"),  # success/failure/pending/error
                "url": s.get("target_url"),
            }
        )
    for c in check_runs:
        items.append(
            {
                "name": c.get("name", "check"),
                "status": c.get("status"),  # queued/in_progress/completed
                "conclusion": c.get("conclusion"),  # success/failure/...
                "url": c.get("html_url"),
            }
        )

    # 汇总：任一 failure → failure；任一 in_progress/pending → pending；全 success → success
    def _bad(it: dict) -> bool:
        return it["conclusion"] in ("failure", "error", "timed_out", "cancelled")

    def _pending(it: dict) -> bool:
        return it["status"] != "completed" or it["conclusion"] in (None, "pending")

    overall = "success"
    if not items:
        overall = "none"
    elif any(_bad(it) for it in items):
        overall = "failure"
    elif any(_pending(it) for it in items):
        overall = "pending"
    return {"overall": overall, "checks": items}


@router.get("/{number}")
async def get_pr(
    number: int,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """单个 PR 的详情：基本信息 + 改了哪些文件 + CI 状态 + 评论。"""
    try:
        pr = await gh.get_pr(repo, number)
        files = await gh.list_pr_files(repo, number)
        head_sha = pr["head"]["sha"]
        combined = await gh.get_combined_status(repo, head_sha)
        check_runs = await gh.list_check_runs(repo, head_sha)
        comments = await gh.list_pr_comments(repo, number)
    except GitHubNotFound:
        raise HTTPException(404, f"PR #{number} 不存在")
    except GitHubError as e:
        raise HTTPException(e.status, e.message)

    return {
        "pr": _summarize_pr(pr),
        "body": pr.get("body") or "",
        "files": [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
            }
            for f in files
        ],
        "checks": _checks_summary(combined, check_runs),
        "comments": [
            {
                "user": c["user"]["login"] if c.get("user") else None,
                "body": c["body"],
                "created_at": c["created_at"],
                "html_url": c["html_url"],
            }
            for c in comments
        ],
    }


class CreatePrIn(BaseModel):
    head: str
    base: str = "main"
    title: str | None = None
    body: str = ""
    draft: bool = False


@router.post("")
async def create_pr(
    body: CreatePrIn,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """从 head 分支（一般是 ai/*）开一个 PR 到 base。

    若该 head→base 已有 open PR，则直接返回那个，不重复开。
    """
    title = body.title or f"采纳 {body.head}"
    # 先查是否已有 open PR
    try:
        existing = await gh.list_prs(repo, state="open", head=body.head, base=body.base)
        if existing:
            logger.info("create_pr: reuse existing #{}", existing[0]["number"])
            return {"ok": True, "reused": True, "pr": _summarize_pr(existing[0])}
        pr = await gh.open_pr(
            repo,
            title=title,
            head=body.head,
            base=body.base,
            body=body.body,
            draft=body.draft,
        )
    except GitHubError as e:
        if e.status == 422:
            raise HTTPException(
                422,
                f"开 PR 失败：{e.message}。可能 head 和 base 内容相同，或分支不存在。",
            )
        raise HTTPException(e.status, e.message)
    logger.info("PR opened | repo={} #{} {} → {}", repo, pr["number"], body.head, body.base)
    return {"ok": True, "reused": False, "pr": _summarize_pr(pr)}


class CommentIn(BaseModel):
    body: str


@router.post("/{number}/comment")
async def comment_pr(
    number: int,
    payload: CommentIn,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """在 PR 上发一条讨论评论。"""
    if not payload.body.strip():
        raise HTTPException(400, "评论内容不能为空")
    try:
        c = await gh.create_pr_comment(repo, number, payload.body)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {
        "ok": True,
        "comment": {
            "user": c["user"]["login"] if c.get("user") else None,
            "body": c["body"],
            "created_at": c["created_at"],
            "html_url": c["html_url"],
        },
    }


class MergePrIn(BaseModel):
    method: str = "squash"  # squash | merge | rebase
    delete_branch: bool = True
    dispatch_pages: bool = True


@router.post("/{number}/merge")
async def merge_pr(
    number: int,
    body: MergePrIn,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """合并 PR（默认 squash），可顺带删 head 分支 + 刷新预览。"""
    if body.method not in ("squash", "merge", "rebase"):
        raise HTTPException(400, "method 只能是 squash / merge / rebase")
    try:
        pr = await gh.get_pr(repo, number)
        head_ref = pr["head"]["ref"]
        base_ref = pr["base"]["ref"]
        result = await gh.merge_pr(repo, number, method=body.method)
    except GitHubNotFound:
        raise HTTPException(404, f"PR #{number} 不存在")
    except GitHubError as e:
        if e.status == 405:
            raise HTTPException(405, f"无法合并（可能有冲突或 CI 未过）：{e.message}")
        if e.status == 409:
            raise HTTPException(409, f"合并冲突，需要人工解决：{e.message}")
        raise HTTPException(e.status, e.message)

    branch_deleted = False
    if body.delete_branch and head_ref.startswith("ai/"):
        try:
            await gh.delete_branch(repo, head_ref)
            branch_deleted = True
        except (GitHubNotFound, GitHubError) as e:
            logger.warning("delete branch after merge failed (non-fatal): {}", e)

    pages_dispatched = False
    if body.dispatch_pages:
        try:
            await gh.dispatch_workflow(repo, PAGES_WORKFLOW, ref=base_ref)
            pages_dispatched = True
        except GitHubError as e:
            logger.warning("post-merge pages dispatch failed: {}", e)

    logger.info("PR merged | repo={} #{} method={}", repo, number, body.method)
    return {
        "ok": True,
        "merged": result.get("merged", True),
        "sha": result.get("sha"),
        "branch_deleted": branch_deleted,
        "pages_dispatched": pages_dispatched,
        "base": base_ref,
    }


@router.post("/{number}/close")
async def close_pr(
    number: int,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """关闭 PR（不合并）。"""
    try:
        await gh.close_pr(repo, number)
    except GitHubNotFound:
        raise HTTPException(404, f"PR #{number} 不存在")
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {"ok": True, "closed": number}
