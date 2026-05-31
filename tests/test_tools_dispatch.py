"""tools.dispatch 工具执行边界的离线单测（无网络）。

dispatch 是 agent loop 调用工具的统一入口：任何工具失败都要变成
{ok:False, error:...} 让 AI 自己反思，而不是把 agent 循环搞崩。
另含 schema↔handler 一致性守卫（防止以后加了 schema 忘了 handler）。
运行（项目根）：conda run -n appdev python -m pytest tests/ -q
"""

import asyncio
import json

import pytest

from backend.app.ai import tools
from backend.app.ai.tools import dispatch, tool_result_to_message
from backend.app.github.errors import GitHubError


def _run(coro):
    return asyncio.run(coro)


# ----------------------------- dispatch 错误兜底 -----------------------------

def test_unknown_tool():
    r = _run(dispatch(None, "o/r", "no_such_tool", {}))
    assert r["ok"] is False
    assert "unknown tool" in r["error"]


def test_success_path(monkeypatch):
    async def _ok(gh, repo, args):
        return {"echo": args.get("v")}
    monkeypatch.setitem(tools.HANDLERS, "_t_ok", _ok)
    r = _run(dispatch(None, "o/r", "_t_ok", {"v": 42}))
    assert r == {"ok": True, "result": {"echo": 42}}


def test_value_error_becomes_bad_arguments(monkeypatch):
    async def _bad(gh, repo, args):
        raise ValueError("缺 path")
    monkeypatch.setitem(tools.HANDLERS, "_t_bad", _bad)
    r = _run(dispatch(None, "o/r", "_t_bad", {}))
    assert r["ok"] is False
    assert r["error"].startswith("bad arguments:")


def test_github_error_handled(monkeypatch):
    async def _gh(gh, repo, args):
        raise GitHubError(403, "no perm")
    monkeypatch.setitem(tools.HANDLERS, "_t_gh", _gh)
    r = _run(dispatch(None, "o/r", "_t_gh", {}))
    assert r["ok"] is False
    assert "403" in r["error"]


def test_generic_exception_handled(monkeypatch):
    async def _boom(gh, repo, args):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(tools.HANDLERS, "_t_boom", _boom)
    r = _run(dispatch(None, "o/r", "_t_boom", {}))
    assert r["ok"] is False
    assert r["error"].startswith("RuntimeError:")


# ----------------------------- tool_result_to_message -----------------------------

def test_tool_result_to_message_shape():
    msg = tool_result_to_message("call_1", "read_file", {"ok": True, "result": {"a": 1}})
    assert msg["role"] == "tool"
    assert msg["tool_call_id"] == "call_1"
    assert msg["name"] == "read_file"
    # content 是合法 JSON 字符串
    assert json.loads(msg["content"]) == {"ok": True, "result": {"a": 1}}


def test_tool_result_to_message_non_ascii_preserved():
    msg = tool_result_to_message("c", "x", {"msg": "中文"})
    assert "中文" in msg["content"]  # ensure_ascii=False


# ----------------------------- schema ↔ handler 一致性 -----------------------------

def test_every_schema_has_handler():
    schema_names = {t["function"]["name"] for t in tools.TOOL_SCHEMAS}
    missing = schema_names - set(tools.HANDLERS)
    assert not missing, f"这些工具有 schema 但没 handler: {missing}"


def test_every_handler_has_schema():
    schema_names = {t["function"]["name"] for t in tools.TOOL_SCHEMAS}
    extra = set(tools.HANDLERS) - schema_names
    assert not extra, f"这些 handler 没有对应 schema（AI 看不到）: {extra}"


def test_schema_well_formed():
    for t in tools.TOOL_SCHEMAS:
        assert t["type"] == "function"
        fn = t["function"]
        assert fn["name"] and isinstance(fn["name"], str)
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"
