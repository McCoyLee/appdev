"""凭据连通性探测端点。供前端「测试」按钮实时校验用户填的 token / key。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from ..ai.providers.base import Provider
from ..github.client import GitHubClient
from ..github.errors import GitHubError
from .deps import github_client, require_provider

router = APIRouter(prefix="/api/probe", tags=["probe"])


@router.get("/github")
async def probe_github(gh: GitHubClient = Depends(github_client)):
    """用 header 里的 GitHub token 试着调 /user 验证有效性。"""
    try:
        me = await gh.whoami()
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {
        "ok": True,
        "login": me["login"],
        "avatar_url": me.get("avatar_url"),
        "name": me.get("name"),
    }


@router.get("/github/repos")
async def list_my_repos(
    gh: GitHubClient = Depends(github_client),
    per_page: int = 30,
):
    """列出当前 token 能访问的仓库（用于仓库下拉）。"""
    try:
        repos = await gh._request(
            "GET",
            "/user/repos",
            params={"per_page": per_page, "sort": "updated", "affiliation": "owner,collaborator"},
        )
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {
        "repos": [
            {
                "full_name": r["full_name"],
                "private": r["private"],
                "default_branch": r.get("default_branch", "main"),
                "size": r.get("size", 0),
                "updated_at": r.get("updated_at"),
            }
            for r in repos
        ]
    }


@router.post("/ai")
async def probe_ai(provider: Provider = Depends(require_provider)):
    """用 header 里的 AI key 试着发一个极小请求验证。"""
    try:
        msg = await provider.chat(
            messages=[{"role": "user", "content": "回复一个字：好"}],
            tools=None,
            temperature=0.0,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("ai probe failed: {}", e)
        raise HTTPException(401, f"AI provider 调用失败：{type(e).__name__}: {e}")
    return {
        "ok": True,
        "provider": provider.name,
        "sample_reply": (msg.content or "")[:40],
        "usage": msg.usage,
    }
