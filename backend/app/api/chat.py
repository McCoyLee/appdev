"""SSE 流式 agent 对话接口。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..ai.agent import Agent
from ..ai.providers.base import Provider
from ..github.client import GitHubClient
from .deps import github_client, require_provider, require_repo

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str = ""
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    max_iterations: int = Field(8, ge=1, le=20)


@router.post("/chat")
async def chat(
    body: ChatIn,
    repo: str = Depends(require_repo),
    provider: Provider = Depends(require_provider),
    gh: GitHubClient = Depends(github_client),
):
    history: list[dict[str, Any]] = [m.model_dump(exclude_none=True) for m in body.messages]
    logger.info("chat | repo={} | msgs={}", repo, len(history))

    agent = Agent(provider, gh, repo, max_iterations=body.max_iterations)

    async def stream():
        try:
            async for ev in agent.run(history):
                yield {
                    "event": ev.type,
                    "data": json.dumps(ev.data, ensure_ascii=False, default=str),
                }
        except Exception as e:  # noqa: BLE001
            logger.exception("chat stream error")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(stream())
