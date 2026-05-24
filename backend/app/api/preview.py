"""预览部署相关端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from ..github.client import GitHubClient
from ..github.errors import GitHubError
from .deps import github_client, require_repo

router = APIRouter(prefix="/api/preview", tags=["preview"])

PAGES_WORKFLOW = "pages.yml"


@router.get("")
async def preview_status(
    branch: str = Query(..., description="要查看预览状态的分支，如 ai/xxx 或 main"),
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """
    返回预览部署的当前状态。
    单环境模式：URL 永远是 Pages 主 URL，但内容是最后一次 dispatch 的分支。
    """
    try:
        pages = await gh.get_pages_info(repo)
        # 找该分支最新的 pages.yml run
        runs = await gh.list_runs(repo, workflow=PAGES_WORKFLOW, branch=branch, per_page=1)
        latest = runs[0] if runs else None
    except GitHubError as e:
        raise HTTPException(e.status, e.message)

    setup_hint = None
    if pages is None:
        setup_hint = (
            f"还未启用 GitHub Pages。去 https://github.com/{repo}/settings/pages "
            "把 Source 选成 'GitHub Actions'，下次部署就能用了。"
        )

    return {
        "branch": branch,
        "pages_enabled": pages is not None,
        "deployment_url": pages.get("html_url") if pages else None,
        "latest_run": _summarize_run(latest) if latest else None,
        "setup_hint": setup_hint,
    }


@router.post("/trigger")
async def trigger_preview(
    branch: str = Query(...),
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """手动派发预览部署（也可由 agent 自动触发）。"""
    try:
        await gh.dispatch_workflow(repo, PAGES_WORKFLOW, ref=branch)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    logger.info("preview dispatched | repo={} branch={}", repo, branch)
    return {"ok": True, "branch": branch}


@router.post("/setup-environment")
async def setup_pages_environment(
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """
    一键把 github-pages environment 的 deployment branch policy 改成无限制，
    让 ai/* 分支也能部署到 Pages。
    """
    try:
        await gh._request(
            "PUT",
            f"/repos/{repo}/environments/github-pages",
            json={"deployment_branch_policy": None},
        )
    except GitHubError as e:
        if e.status == 403:
            raise HTTPException(
                403,
                "GitHub token 缺少 Environments 写权限。请到 PAT 设置里把 Environments 加成 R/W，或手动去仓库 Settings → Environments → github-pages 选 'No restriction'。",
            )
        if e.status == 404:
            raise HTTPException(
                404,
                "github-pages environment 还不存在；先去 Settings → Pages 启用 Pages（Source 选 GitHub Actions），然后重试。",
            )
        raise HTTPException(e.status, e.message)
    logger.info("github-pages env policy → no restriction | repo={}", repo)
    return {"ok": True, "deployment_branch_policy": None}


def _summarize_run(r: dict) -> dict:
    return {
        "id": r["id"],
        "status": r["status"],
        "conclusion": r["conclusion"],
        "head_sha": r["head_sha"],
        "head_branch": r["head_branch"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
        "html_url": r["html_url"],
    }
