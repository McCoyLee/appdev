"""
AI Provider 抽象。

设计：
- 所有 provider 统一暴露 chat(messages, tools) -> AssistantMessage 接口
- 工具调用沿用 OpenAI / DeepSeek 协议（最广兼容），Claude 适配层做转换
- 流式由调用方决定是否使用（M0 默认非流，M0-4 SSE 时再加流式接口）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class AssistantMessage:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)


class Provider(Protocol):
    name: str

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ) -> AssistantMessage: ...

    async def aclose(self) -> None: ...
