"""FastAPI 依赖：注入 GitHub client + AI provider + 仓库。

M1 凭据优先级：
1. 请求 header（前端 localStorage 传过来）
2. .env 配置（开发期 / 单用户兜底）

支持的 header：
- X-GitHub-Token
- X-AI-Provider（deepseek|claude|...）
- X-AI-Key
- X-Repo（owner/name）
"""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator

from fastapi import Depends, Header, HTTPException, Query

from ..ai.providers.base import Provider
from ..ai.providers.deepseek import DeepSeekProvider
from ..core.config import Settings, get_settings
from ..github.client import GitHubClient


@lru_cache
def _provider_singleton(provider: str, api_key: str, base_url: str, model: str) -> Provider:
    """按 (provider, key) 缓存 provider 实例。"""
    if provider == "deepseek":
        return DeepSeekProvider(api_key=api_key, base_url=base_url, model=model)
    raise HTTPException(400, f"不支持的 AI provider: {provider}")


def require_provider(
    x_ai_provider: str | None = Header(None, alias="X-AI-Provider"),
    x_ai_key: str | None = Header(None, alias="X-AI-Key"),
    x_ai_model: str | None = Header(None, alias="X-AI-Model"),
    s: Settings = Depends(get_settings),
) -> Provider:
    provider_name = (x_ai_provider or "deepseek").lower()
    if provider_name == "deepseek":
        api_key = x_ai_key or s.deepseek_api_key
        if not api_key:
            raise HTTPException(401, "缺少 DeepSeek API key（前端配置或 .env）")
        return _provider_singleton(
            "deepseek",
            api_key,
            s.deepseek_base_url,
            x_ai_model or s.deepseek_model,
        )
    raise HTTPException(400, f"暂不支持的 provider: {provider_name}")


async def github_client(
    x_github_token: str | None = Header(None, alias="X-GitHub-Token"),
    s: Settings = Depends(get_settings),
) -> AsyncIterator[GitHubClient]:
    token = x_github_token or s.github_token
    if not token:
        raise HTTPException(401, "缺少 GitHub token（前端配置或 .env）")
    gh = GitHubClient(token, s.github_api_base)
    try:
        yield gh
    finally:
        await gh.aclose()


def require_repo(
    repo: str | None = Query(None, description="owner/name；优先于 header 和 .env"),
    x_repo: str | None = Header(None, alias="X-Repo"),
    s: Settings = Depends(get_settings),
) -> str:
    target = repo or x_repo or s.test_repo
    if not target or "/" not in target:
        raise HTTPException(400, "缺少有效的 repo，格式 owner/name")
    return target
