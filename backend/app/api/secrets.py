from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..github.client import GitHubClient
from ..github.errors import GitHubError
from .deps import github_client, require_repo

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


class SecretIn(BaseModel):
    name: str = Field(..., pattern=r"^[A-Z_][A-Z0-9_]*$", description="大写下划线，符合环境变量规范")
    value: str = Field(..., min_length=1)


@router.get("")
async def list_secrets_endpoint(
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    try:
        return {"secrets": await gh.list_secrets(repo)}
    except GitHubError as e:
        raise HTTPException(e.status, e.message)


@router.post("")
async def set_secret_endpoint(
    body: SecretIn,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    try:
        await gh.set_secret(repo, body.name, body.value)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {"ok": True, "name": body.name}


@router.delete("/{name}")
async def delete_secret_endpoint(
    name: str,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    try:
        await gh.delete_secret(repo, name)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {"ok": True}
