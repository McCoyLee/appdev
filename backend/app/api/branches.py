"""分支生命周期：列出 AI 分支、采纳（FF merge）、丢弃。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from ..github.client import GitHubClient
from ..github.errors import GitHubError, GitHubNotFound
from .deps import github_client, require_repo

router = APIRouter(prefix="/api/branches", tags=["branches"])

PAGES_WORKFLOW = "pages.yml"


@router.get("")
async def list_ai_branches(
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """列出所有 ai/* 分支（按更新时间倒序）。"""
    try:
        all_branches = await gh._request("GET", f"/repos/{repo}/branches", params={"per_page": 100})
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    ai = [b for b in all_branches if b["name"].startswith("ai/")]
    return {"branches": [{"name": b["name"], "sha": b["commit"]["sha"]} for b in ai]}


class AdoptIn(BaseModel):
    target: str = "main"
    dispatch_pages: bool = True


@router.post("/{branch:path}/adopt")
async def adopt_branch(
    branch: str,
    body: AdoptIn,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """
    采纳 ai/* 分支到 target（默认 main）：
    1. fast-forward target → branch HEAD
    2. 删除 ai/* 分支
    3. 触发 pages.yml on target，让预览回到生产内容
    """
    if not branch.startswith("ai/"):
        raise HTTPException(400, "只能采纳 ai/* 分支")

    strategy = "fast-forward"
    try:
        await gh.fast_forward_merge(repo, base=body.target, head=branch)
    except GitHubError as e:
        if e.status != 422:
            raise HTTPException(e.status, e.message)
        # base 偏离，退回普通 merge（保留所有 commit + 一个 merge commit）
        logger.info("ff failed → falling back to merge commit | branch={}", branch)
        try:
            await gh.merge_branch(
                repo,
                base=body.target,
                head=branch,
                message=f"采纳 AI 分支 {branch}",
            )
            strategy = "merge-commit"
        except GitHubError as e2:
            if e2.status == 409:
                raise HTTPException(409, f"合并冲突，需要人工解决：{e2.message}")
            raise HTTPException(e2.status, e2.message)

    try:
        await gh.delete_branch(repo, branch)
    except GitHubNotFound:
        pass
    except GitHubError as e:
        logger.warning("delete branch failed (non-fatal): {}", e)

    pages_dispatched = False
    if body.dispatch_pages:
        try:
            await gh.dispatch_workflow(repo, PAGES_WORKFLOW, ref=body.target)
            pages_dispatched = True
        except GitHubError as e:
            logger.warning("post-adopt pages dispatch failed: {}", e)

    logger.info("adopted | repo={} branch={} → {} | strategy={}", repo, branch, body.target, strategy)
    return {
        "ok": True,
        "adopted_from": branch,
        "target": body.target,
        "strategy": strategy,
        "pages_dispatched": pages_dispatched,
    }


class DiscardIn(BaseModel):
    branch: str


@router.post("/discard")
async def discard_branch(
    body: DiscardIn,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """丢弃 ai/* 分支（用户点「再改改」改不动了或不想要的时候）。"""
    if not body.branch.startswith("ai/"):
        raise HTTPException(400, "只能丢弃 ai/* 分支")
    try:
        await gh.delete_branch(repo, body.branch)
    except GitHubNotFound:
        pass
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {"ok": True, "discarded": body.branch}
