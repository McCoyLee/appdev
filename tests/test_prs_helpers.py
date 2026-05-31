"""prs.py 里几个纯函数的离线单测（无网络，跑得快）。

锁住 M4 PR 协作的核心逻辑：CI 状态汇总 / patch 截断 / PR 摘要。
运行（项目根）：conda run -n appdev python -m pytest tests/ -q
"""

from backend.app.api.prs import (
    MAX_PATCH_CHARS,
    _checks_summary,
    _summarize_pr,
    _truncate_patch,
)


# ----------------------------- _truncate_patch -----------------------------

def test_truncate_patch_none():
    assert _truncate_patch(None) is None


def test_truncate_patch_short_unchanged():
    p = "@@ -0,0 +1 @@\n+hello"
    assert _truncate_patch(p) == p


def test_truncate_patch_long_truncated():
    p = "x" * (MAX_PATCH_CHARS + 100)
    out = _truncate_patch(p)
    assert len(out) < len(p)
    assert out.startswith("x" * 10)
    assert "截断" in out


# ----------------------------- _checks_summary -----------------------------

def test_checks_summary_empty_is_none():
    assert _checks_summary({"statuses": []}, [])["overall"] == "none"


def test_checks_summary_all_success():
    combined = {"statuses": [{"context": "legacy", "state": "success"}]}
    runs = [{"name": "CI", "status": "completed", "conclusion": "success"}]
    s = _checks_summary(combined, runs)
    assert s["overall"] == "success"
    assert len(s["checks"]) == 2


def test_checks_summary_failure_wins():
    combined = {"statuses": []}
    runs = [
        {"name": "CI", "status": "completed", "conclusion": "success"},
        {"name": "lint", "status": "completed", "conclusion": "failure"},
    ]
    assert _checks_summary(combined, runs)["overall"] == "failure"


def test_checks_summary_pending_when_in_progress():
    combined = {"statuses": []}
    runs = [{"name": "CI", "status": "in_progress", "conclusion": None}]
    assert _checks_summary(combined, runs)["overall"] == "pending"


def test_checks_summary_legacy_pending_state():
    combined = {"statuses": [{"context": "deploy", "state": "pending"}]}
    assert _checks_summary(combined, [])["overall"] == "pending"


def test_checks_summary_error_counts_as_failure():
    combined = {"statuses": [{"context": "x", "state": "error"}]}
    assert _checks_summary(combined, [])["overall"] == "failure"


# ----------------------------- _summarize_pr -----------------------------

def _fake_pr(**over):
    base = {
        "number": 7,
        "title": "标题",
        "state": "open",
        "draft": False,
        "merged": False,
        "head": {"ref": "ai/x", "sha": "abc123"},
        "base": {"ref": "main"},
        "user": {"login": "alice"},
        "html_url": "https://github.com/o/r/pull/7",
        "comments": 2,
        "mergeable": True,
        "mergeable_state": "clean",
        "additions": 10,
        "deletions": 3,
        "changed_files": 2,
        "created_at": "2026-05-31T00:00:00Z",
        "updated_at": "2026-05-31T01:00:00Z",
    }
    base.update(over)
    return base


def test_summarize_pr_maps_nested_refs():
    s = _summarize_pr(_fake_pr())
    assert s["head"] == "ai/x"
    assert s["head_sha"] == "abc123"
    assert s["base"] == "main"
    assert s["user"] == "alice"
    assert s["number"] == 7


def test_summarize_pr_handles_null_user():
    s = _summarize_pr(_fake_pr(user=None))
    assert s["user"] is None
