"""
Agent 循环。

输入：用户消息 + 仓库 + 会话历史
输出：完整的对话步骤流（assistant 文本 / tool_call / tool_result 三类事件）

接口设计成 async generator，方便上层用 SSE 推流。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator

from loguru import logger

from ..github.client import GitHubClient
from ..github.errors import GitHubError
from .prompts import SYSTEM_PROMPT_ZH
from .providers.base import AssistantMessage, Provider
from .tools import TOOL_SCHEMAS, dispatch, tool_result_to_message

PREVIEW_WORKFLOW = "pages.yml"


@dataclass
class AgentEvent:
    type: str  # "assistant_text" | "tool_call" | "tool_result" | "usage" | "done" | "error"
    data: dict


class Agent:
    def __init__(
        self,
        provider: Provider,
        github: GitHubClient,
        repo: str,
        max_iterations: int = 8,
    ) -> None:
        self.provider = provider
        self.github = github
        self.repo = repo
        self.max_iterations = max_iterations

    def build_system(self) -> str:
        return SYSTEM_PROMPT_ZH + f"\n【当前仓库】{self.repo}\n"

    async def run(self, history: list[dict[str, Any]]) -> AsyncIterator[AgentEvent]:
        """
        history 形如 [{"role":"user","content":"..."}] 或包含历史 assistant/tool 消息。
        系统消息由本方法注入，调用方不需要传。
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.build_system()},
            *history,
        ]

        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        touched_branch: str | None = None  # 跟踪 AI 修改过的 ai/* 分支，用于自动派发预览

        for step in range(self.max_iterations):
            logger.debug("agent iter {} | messages={}", step, len(messages))
            try:
                assistant: AssistantMessage = await self.provider.chat(
                    messages, tools=TOOL_SCHEMAS
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("provider chat failed")
                yield AgentEvent("error", {"message": f"AI 调用失败: {e}"})
                return

            for k in total_usage:
                total_usage[k] += int(assistant.usage.get(k, 0) or 0)

            # 把 assistant 消息加回历史
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": assistant.content}
            if assistant.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _to_json_args(tc.arguments),
                        },
                    }
                    for tc in assistant.tool_calls
                ]
            messages.append(assistant_msg)

            if assistant.content:
                yield AgentEvent("assistant_text", {"content": assistant.content})

            # 没有工具调用 → 结束
            if not assistant.tool_calls:
                async for ev in self._post_run_preview(touched_branch):
                    yield ev
                yield AgentEvent("usage", total_usage)
                yield AgentEvent("done", {"finish_reason": assistant.finish_reason})
                return

            # 执行所有工具
            for tc in assistant.tool_calls:
                yield AgentEvent(
                    "tool_call",
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments},
                )
                payload = await dispatch(self.github, self.repo, tc.name, tc.arguments)
                yield AgentEvent(
                    "tool_result",
                    {"id": tc.id, "name": tc.name, "payload": payload},
                )
                messages.append(tool_result_to_message(tc.id, tc.name, payload))

                # 跟踪 ai/* 分支的写入操作
                if payload.get("ok") and tc.name in ("write_file", "write_files", "ensure_branch"):
                    br = tc.arguments.get("branch")
                    if br and br.startswith("ai/"):
                        touched_branch = br

        # 超出迭代上限
        async for ev in self._post_run_preview(touched_branch):
            yield ev
        yield AgentEvent("usage", total_usage)
        yield AgentEvent(
            "error",
            {"message": f"超出最大迭代次数 {self.max_iterations}，对话中止"},
        )

    async def _post_run_preview(self, branch: str | None) -> AsyncIterator[AgentEvent]:
        """agent.run 结束后，如果改过 ai/* 分支，自动派发 Pages 部署。"""
        if not branch:
            return
        try:
            await self.github.dispatch_workflow(self.repo, PREVIEW_WORKFLOW, ref=branch)
            logger.info("auto-preview dispatched | branch={}", branch)
            yield AgentEvent(
                "preview_triggered",
                {"branch": branch, "workflow": PREVIEW_WORKFLOW},
            )
        except GitHubError as e:
            logger.warning("auto-preview failed: {}", e)
            yield AgentEvent(
                "preview_error",
                {"branch": branch, "message": str(e)},
            )


def _to_json_args(args: dict) -> str:
    import json

    return json.dumps(args, ensure_ascii=False)
