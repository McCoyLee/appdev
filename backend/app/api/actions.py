from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..github.client import GitHubClient
from ..github.errors import GitHubError
from .deps import github_client, require_repo

router = APIRouter(prefix="/api", tags=["actions"])


@router.get("/workflows")
async def workflows(
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    try:
        wfs = await gh.list_workflows(repo)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {
        "workflows": [
            {"id": w["id"], "name": w["name"], "path": w["path"], "state": w["state"]}
            for w in wfs
        ]
    }


@router.get("/runs")
async def runs(
    workflow: str | None = Query(None),
    per_page: int = Query(10, ge=1, le=50),
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    try:
        rs = await gh.list_runs(repo, workflow=workflow, per_page=per_page)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {
        "runs": [
            {
                "id": r["id"],
                "name": r["name"],
                "status": r["status"],
                "conclusion": r["conclusion"],
                "head_branch": r["head_branch"],
                "created_at": r["created_at"],
                "html_url": r["html_url"],
            }
            for r in rs
        ]
    }


class DispatchIn(BaseModel):
    workflow: str
    ref: str = "main"
    inputs: dict = {}


@router.post("/runs/dispatch")
async def dispatch(
    body: DispatchIn,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    try:
        await gh.dispatch_workflow(repo, body.workflow, ref=body.ref, inputs=body.inputs)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)
    return {"ok": True}
