from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..github.client import GitHubClient
from ..github.errors import GitHubError
from .deps import github_client, require_repo

router = APIRouter(prefix="/api/repo", tags=["repo"])


@router.get("/info")
async def repo_info(
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    me = await gh.whoami()
    info = await gh.get_repo(repo)
    return {
        "user": {"login": me["login"], "avatar_url": me.get("avatar_url")},
        "repo": {
            "full_name": info["full_name"],
            "default_branch": info["default_branch"],
            "private": info["private"],
            "html_url": info["html_url"],
            "permissions": info.get("permissions", {}),
        },
    }


@router.get("/tree")
async def repo_tree(
    path: str = Query("", description="留空=根目录"),
    ref: str | None = Query(None),
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    return {"path": path, "ref": ref, "entries": await gh.list_dir(repo, path, ref=ref)}


@router.get("/file")
async def repo_file(
    path: str = Query(...),
    ref: str | None = Query(None),
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    try:
        return await gh.read_file(repo, path, ref=ref)
    except GitHubError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=e.status, detail=e.message)
