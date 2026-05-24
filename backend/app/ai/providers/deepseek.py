"""
DeepSeek provider，走 OpenAI 兼容 API。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from .base import AssistantMessage, ToolCall


class DeepSeekProvider:
    name = "deepseek"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ) -> AssistantMessage:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                logger.warning("tool args not JSON: {}", tc.function.arguments)
                args = {"_raw": tc.function.arguments}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        return AssistantMessage(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=resp.usage.model_dump() if resp.usage else {},
        )

    async def aclose(self) -> None:
        await self._client.close()
