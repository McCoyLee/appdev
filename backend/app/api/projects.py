"""新建项目：在用户 GitHub 名下创建仓库 + 推模板内容 + 启用 Pages + 放开分支策略。

一站式 API，目标是把"从想造应用到能跟 AI 聊"压到 30 秒。
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, field_validator
from sse_starlette.sse import EventSourceResponse

from ..github.client import GitHubClient
from ..github.errors import GitHubError
from .deps import github_client

router = APIRouter(prefix="/api/projects", tags=["projects"])

TEMPLATES_ROOT = Path(__file__).resolve().parents[3] / "templates"
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")


class CreateProjectIn(BaseModel):
    template_id: str = Field(..., description="模板 ID，对应 templates/<id>/")
    name: str = Field(..., min_length=1, max_length=80)
    private: bool = False
    description: str = ""
    org: str | None = Field(None, description="若指定则在 org 下创建，否则在用户名下")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not NAME_PATTERN.match(v):
            raise ValueError("仓库名只允许字母/数字/. _ - ")
        return v

    @field_validator("template_id")
    @classmethod
    def validate_template(cls, v: str) -> str:
        if not (TEMPLATES_ROOT / v).is_dir():
            raise ValueError(f"模板 {v} 不存在")
        return v


def _load_template_files(template_id: str) -> list[dict]:
    """读取模板目录所有文件（排除 template.json）。"""
    root = TEMPLATES_ROOT / template_id
    files: list[dict] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel == "template.json":
            continue
        files.append({"path": rel, "content": p.read_text(encoding="utf-8")})
    return files


@router.post("/create")
async def create_project(
    body: CreateProjectIn,
    gh: GitHubClient = Depends(github_client),
):
    """同步创建：创建仓库 + 推模板 + 启用 Pages + 放开分支策略。

    需要 PAT 有 Account Permissions → 'Repository creation' R/W。
    没这个权限请改走 /api/projects/init（推到你手动建好的空仓库）。
    """
    steps: list[dict] = []

    # 1. 创建仓库
    try:
        repo_data = await gh.create_repo(
            name=body.name,
            private=body.private,
            description=body.description or f"Created from template {body.template_id}",
            auto_init=True,
            org=body.org,
        )
    except GitHubError as e:
        if e.status == 422:
            raise HTTPException(422, f"仓库已存在或名字冲突：{e.message}")
        if e.status == 403:
            raise HTTPException(
                403,
                "PAT 不能创建仓库。两个解法：(1) 去 PAT 设置里加 'Account Permissions → Repository creation' R/W；(2) 你先在 GitHub 上手动建一个空仓库，然后用「使用已有仓库」按钮（/api/projects/init）。",
            )
        raise HTTPException(e.status, e.message)

    repo = repo_data["full_name"]
    default_branch = repo_data.get("default_branch", "main")
    html_url = repo_data["html_url"]
    steps.append({"step": "create_repo", "ok": True, "repo": repo})

    # 2. 等 GitHub provision 默认分支
    await asyncio.sleep(2)

    # 3. 推模板内容（一个 commit 多文件）
    files = _load_template_files(body.template_id)
    try:
        commit = await gh.write_files(
            repo,
            branch=default_branch,
            files=files,
            message=f"[init] {body.template_id} 模板",
        )
        steps.append({"step": "push_template", "ok": True, "files": len(files), "commit": commit["commit_sha"][:7]})
    except GitHubError as e:
        steps.append({"step": "push_template", "ok": False, "error": str(e)})
        raise HTTPException(500, f"创建了仓库 {repo} 但推模板失败：{e}")

    # 4. 启用 Pages（仅静态站类型需要）
    pages_enabled = False
    pages_url = None
    needs_pages = body.template_id in ("static-site",)  # 后续可在 template.json 标注
    if needs_pages:
        try:
            pages = await gh.enable_pages(repo, build_type="workflow")
            pages_enabled = True
            pages_url = pages.get("html_url") if isinstance(pages, dict) else None
            steps.append({"step": "enable_pages", "ok": True, "url": pages_url})
        except GitHubError as e:
            steps.append({"step": "enable_pages", "ok": False, "error": str(e)})
            logger.warning("enable_pages failed (non-fatal): {}", e)

    # 5. 放开 github-pages 分支策略（best-effort）
    branch_policy_open = False
    if pages_enabled:
        try:
            await gh.open_environment_branches(repo, "github-pages")
            branch_policy_open = True
            steps.append({"step": "open_branch_policy", "ok": True})
        except GitHubError as e:
            steps.append({"step": "open_branch_policy", "ok": False, "error": str(e)})
            logger.warning("open_branch_policy failed (non-fatal): {}", e)

    logger.info("project created | repo={} template={}", repo, body.template_id)
    return {
        "ok": True,
        "repo": repo,
        "html_url": html_url,
        "default_branch": default_branch,
        "template_id": body.template_id,
        "pages_enabled": pages_enabled,
        "pages_url": pages_url,
        "branch_policy_open": branch_policy_open,
        "steps": steps,
    }


class InitProjectIn(BaseModel):
    template_id: str
    repo: str = Field(..., description="owner/name；必须是你已经建好的空仓库或要被覆盖的仓库")
    overwrite: bool = Field(False, description="覆盖已有文件（同名）")

    @field_validator("template_id")
    @classmethod
    def validate_template(cls, v: str) -> str:
        if not (TEMPLATES_ROOT / v).is_dir():
            raise ValueError(f"模板 {v} 不存在")
        return v


@router.post("/init")
async def init_existing_repo(
    body: InitProjectIn,
    gh: GitHubClient = Depends(github_client),
):
    """把模板推到用户**已经建好**的仓库（避免 PAT 创建权限要求）。

    适合场景：用户先在 GitHub UI 上点 New repository（带或不带默认 README），
    然后在我们 UI 上选模板把内容推进去。
    """
    # 1. 仓库可访问性
    try:
        info = await gh.get_repo(body.repo)
    except GitHubError as e:
        if e.status == 404:
            raise HTTPException(404, f"仓库 {body.repo} 不存在或 PAT 无访问权限")
        raise HTTPException(e.status, e.message)

    default_branch = info.get("default_branch", "main")
    branch_exists = bool(await gh.get_branch(body.repo, default_branch))

    # 2. 加载模板
    files = _load_template_files(body.template_id)
    paths = {f["path"] for f in files}

    # 3. 推送：write_files 要求 branch 存在
    if not branch_exists:
        raise HTTPException(
            400,
            f"仓库 {body.repo} 的 {default_branch} 分支不存在（空仓库需要在 GitHub UI 上勾选 'Add a README'）。",
        )

    try:
        commit = await gh.write_files(
            body.repo,
            branch=default_branch,
            files=files,
            message=f"[init] {body.template_id} 模板",
        )
    except GitHubError as e:
        raise HTTPException(e.status, f"推模板失败：{e.message}")

    # 4. 启用 Pages（静态站）
    pages_enabled = False
    pages_url = None
    branch_policy_open = False
    if body.template_id == "static-site":
        try:
            pages = await gh.enable_pages(body.repo, build_type="workflow")
            pages_enabled = True
            pages_url = pages.get("html_url") if isinstance(pages, dict) else None
        except GitHubError as e:
            logger.warning("enable_pages failed: {}", e)
        if pages_enabled:
            try:
                await gh.open_environment_branches(body.repo, "github-pages")
                branch_policy_open = True
            except GitHubError as e:
                logger.warning("open_branch_policy failed: {}", e)

    logger.info("project init from existing repo | repo={} files={}", body.repo, len(files))
    return {
        "ok": True,
        "repo": body.repo,
        "html_url": info["html_url"],
        "default_branch": default_branch,
        "template_id": body.template_id,
        "files_pushed": len(files),
        "commit": commit["commit_sha"][:7],
        "pages_enabled": pages_enabled,
        "pages_url": pages_url,
        "branch_policy_open": branch_policy_open,
    }


@router.post("/create-stream")
async def create_project_stream(
    body: CreateProjectIn,
    gh: GitHubClient = Depends(github_client),
):
    """SSE 流式创建：每步推一个事件，UI 可以渲染进度条。"""

    async def stream():
        def evt(name: str, data: dict):
            return {"event": name, "data": json.dumps(data, ensure_ascii=False, default=str)}

        # 1. create repo
        yield evt("progress", {"step": "create_repo", "status": "running"})
        try:
            repo_data = await gh.create_repo(
                name=body.name,
                private=body.private,
                description=body.description or f"Created from template {body.template_id}",
                auto_init=True,
                org=body.org,
            )
        except GitHubError as e:
            yield evt("error", {"step": "create_repo", "message": str(e)})
            return
        repo = repo_data["full_name"]
        default_branch = repo_data.get("default_branch", "main")
        yield evt("progress", {"step": "create_repo", "status": "done", "repo": repo, "html_url": repo_data["html_url"]})

        await asyncio.sleep(2)

        # 2. push template
        yield evt("progress", {"step": "push_template", "status": "running"})
        files = _load_template_files(body.template_id)
        try:
            commit = await gh.write_files(
                repo,
                branch=default_branch,
                files=files,
                message=f"[init] {body.template_id} 模板",
            )
        except GitHubError as e:
            yield evt("error", {"step": "push_template", "message": str(e), "repo": repo})
            return
        yield evt("progress", {"step": "push_template", "status": "done", "files": len(files), "commit": commit["commit_sha"][:7]})

        # 3. enable Pages（静态站才需要）
        if body.template_id in ("static-site",):
            yield evt("progress", {"step": "enable_pages", "status": "running"})
            try:
                pages = await gh.enable_pages(repo, build_type="workflow")
                pages_url = pages.get("html_url") if isinstance(pages, dict) else None
                yield evt("progress", {"step": "enable_pages", "status": "done", "url": pages_url})
            except GitHubError as e:
                yield evt("progress", {"step": "enable_pages", "status": "skipped", "error": str(e)})

            yield evt("progress", {"step": "open_branch_policy", "status": "running"})
            try:
                await gh.open_environment_branches(repo, "github-pages")
                yield evt("progress", {"step": "open_branch_policy", "status": "done"})
            except GitHubError as e:
                yield evt("progress", {"step": "open_branch_policy", "status": "skipped", "error": str(e)})

        yield evt("done", {"repo": repo, "html_url": repo_data["html_url"], "default_branch": default_branch, "template_id": body.template_id})

    return EventSourceResponse(stream())
