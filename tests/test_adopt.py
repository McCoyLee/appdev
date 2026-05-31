"""adopt_branch「就这版」采纳逻辑的离线单测（用假 GitHub client，无网络）。

这是全 app 最关键也最容易出错的路径：FF → squash-rebase → FF → merge-commit
三级兜底。这里不碰真 GitHub，纯验证「在什么失败下走哪条分支、返回什么 strategy」。
运行（项目根）：conda run -n appdev python -m pytest tests/ -q
"""

import asyncio

import pytest

from backend.app.api.branches import AdoptIn, adopt_branch
from backend.app.github.errors import GitHubError, GitHubNotFound


class FakeGH:
    """只实现 adopt_branch 用到的方法，按配置模拟失败。"""

    def __init__(self, ff_fail_first=False, rebase_fail=False, merge_status=None,
                 delete_exc=None, dispatch_fail=False):
        self.calls = []
        self.ff_attempts = 0
        self.ff_fail_first = ff_fail_first
        self.rebase_fail = rebase_fail
        self.merge_status = merge_status  # 设了就让 merge_branch 抛该 status
        self.delete_exc = delete_exc
        self.dispatch_fail = dispatch_fail

    async def fast_forward_merge(self, repo, base, head):
        self.ff_attempts += 1
        self.calls.append(("ff", self.ff_attempts))
        if self.ff_fail_first and self.ff_attempts == 1:
            raise GitHubError(422, "not a fast-forward")
        return {}

    async def squash_rebase_branch(self, repo, ai_branch, target):
        self.calls.append(("rebase",))
        if self.rebase_fail:
            raise GitHubError(500, "rebase boom")
        return {"action": "squash-rebased"}

    async def merge_branch(self, repo, base, head, message=None):
        self.calls.append(("merge",))
        if self.merge_status is not None:
            raise GitHubError(self.merge_status, "merge boom")
        return {}

    async def delete_branch(self, repo, branch):
        self.calls.append(("delete",))
        if self.delete_exc is not None:
            raise self.delete_exc

    async def dispatch_workflow(self, repo, workflow, ref):
        self.calls.append(("dispatch", workflow, ref))
        if self.dispatch_fail:
            raise GitHubError(403, "no perm")


def _adopt(gh, branch="ai/x", target="main", dispatch_pages=True):
    body = AdoptIn(target=target, dispatch_pages=dispatch_pages)
    return asyncio.run(adopt_branch(branch, body, repo="o/r", gh=gh))


def _kinds(gh):
    return [c[0] for c in gh.calls]


# ----------------------------- 三级兜底 -----------------------------

def test_happy_fast_forward():
    gh = FakeGH()
    res = _adopt(gh)
    assert res["strategy"] == "fast-forward"
    assert res["ok"] and res["adopted_from"] == "ai/x"
    assert gh.ff_attempts == 1
    assert _kinds(gh) == ["ff", "delete", "dispatch"]


def test_rebase_then_ff_when_ff_422():
    gh = FakeGH(ff_fail_first=True)
    res = _adopt(gh)
    assert res["strategy"] == "rebase-then-ff"
    assert res["rebase_info"] == {"action": "squash-rebased"}
    # 第一次 ff 失败 → rebase → 第二次 ff 成功
    assert _kinds(gh) == ["ff", "rebase", "ff", "delete", "dispatch"]


def test_merge_commit_when_rebase_fails():
    gh = FakeGH(ff_fail_first=True, rebase_fail=True)
    res = _adopt(gh)
    assert res["strategy"] == "merge-commit"
    assert _kinds(gh) == ["ff", "rebase", "merge", "delete", "dispatch"]


def test_merge_conflict_409_raises():
    from fastapi import HTTPException
    gh = FakeGH(ff_fail_first=True, rebase_fail=True, merge_status=409)
    with pytest.raises(HTTPException) as ei:
        _adopt(gh)
    assert ei.value.status_code == 409


# ----------------------------- 守卫 / 非致命错误 -----------------------------

def test_non_ai_branch_rejected():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        _adopt(FakeGH(), branch="main")
    assert ei.value.status_code == 400


def test_delete_not_found_is_non_fatal():
    gh = FakeGH(delete_exc=GitHubNotFound(404, "gone"))
    res = _adopt(gh)  # 不应抛
    assert res["strategy"] == "fast-forward"
    assert res["pages_dispatched"] is True


def test_dispatch_failure_is_non_fatal():
    gh = FakeGH(dispatch_fail=True)
    res = _adopt(gh)
    assert res["ok"] is True
    assert res["pages_dispatched"] is False  # 派发失败但不报错


def test_skip_dispatch_when_disabled():
    gh = FakeGH()
    res = _adopt(gh, dispatch_pages=False)
    assert res["pages_dispatched"] is False
    assert "dispatch" not in _kinds(gh)


def test_ff_non_422_error_propagates():
    from fastapi import HTTPException

    class GH(FakeGH):
        async def fast_forward_merge(self, repo, base, head):
            raise GitHubError(500, "server boom")

    with pytest.raises(HTTPException) as ei:
        _adopt(GH())
    assert ei.value.status_code == 500
