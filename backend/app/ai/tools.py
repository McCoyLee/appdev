"""
工具定义与分发。

AI 看到的工具 schema 与 GitHubClient 方法的桥接。
所有工具都接收一个 `repo` 隐式上下文（不在 schema 里，由 dispatcher 注入），
AI 只关心业务参数，避免它在每次调用重复填仓库名。
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable, Callable

from loguru import logger

from ..github.client import GitHubClient
from ..github.errors import GitHubError

# ---------------- schemas（OpenAI / DeepSeek tool format） ----------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "读取仓库中某个文件。默认返回完整内容；指定 start_line/end_line 时只返回该行号范围。"
                "返回 content / sha / total_lines（更新时需要 sha）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "仓库内相对路径，如 src/app.py"},
                    "ref": {"type": "string", "description": "分支/标签/commit，留空=默认分支"},
                    "start_line": {"type": "integer", "description": "1-based 起始行（含）"},
                    "end_line": {"type": "integer", "description": "1-based 结束行（含）"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出某个目录下的文件与子目录。path 留空=仓库根。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "ref": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "在仓库内搜索代码（GitHub Code Search 语法）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "如 'def login extension:py'"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "创建或更新仓库内**单个**文件。**只能在 ai/* 分支上写**。"
                "更新已存在文件时必须传 sha（先 read_file 拿到）。"
                "**多文件改动请用 write_files，性能更好、原子性更强。**"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "message": {"type": "string", "description": "commit message，简短中文"},
                    "branch": {"type": "string", "description": "目标分支，必须以 ai/ 开头"},
                    "sha": {"type": "string", "description": "更新已有文件时必传"},
                },
                "required": ["path", "content", "message", "branch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_files",
            "description": (
                "**批量**创建或更新多个文件，一个 commit。**只能在 ai/* 分支上写**。"
                "走 Git Data API 创建 blob/tree/commit，原子提交，不需要传每个文件的 sha。"
                "用于：多文件联动修改、模板生成、大改动。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "ai/* 分支"},
                    "message": {"type": "string", "description": "commit message"},
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["path", "content"],
                        },
                        "description": "文件列表",
                    },
                },
                "required": ["branch", "message", "files"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ensure_branch",
            "description": "确保分支存在；不存在则从 from_ref 创建。返回 head commit sha。",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "必须以 ai/ 开头"},
                    "from_ref": {"type": "string", "description": "源分支，通常是 main"},
                },
                "required": ["branch", "from_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_pr",
            "description": "把 ai/* 分支的修改开 PR 到目标分支等待用户审批合并。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "head": {"type": "string", "description": "ai/* 分支"},
                    "base": {"type": "string", "description": "通常 main"},
                    "body": {"type": "string"},
                },
                "required": ["title", "head", "base"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dispatch_workflow",
            "description": "触发一个 GitHub Actions workflow 运行。workflow 是文件名如 ci.yml。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow": {"type": "string"},
                    "ref": {"type": "string", "default": "main"},
                    "inputs": {"type": "object"},
                },
                "required": ["workflow"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_workflows",
            "description": "列出仓库的 workflows。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_runs",
            "description": "列出最近的 workflow 运行记录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow": {"type": "string", "description": "可选，过滤具体 workflow"},
                    "per_page": {"type": "integer", "default": 5},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_secrets",
            "description": "列出仓库 secrets 的名字（看不到值）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_ci",
            "description": (
                "在指定 ai/* 分支上跑 CI workflow（ci.yml），**阻塞等待结果**。"
                "成功返回 {conclusion:'success'}；失败返回失败的 job 名 + 关键日志（末尾 60 行）。"
                "**用法：写完代码后调用一次确认无误；失败时分析日志后修代码再调用一次。**"
                "不要为每个 write_file 都调一次，只在认为完成时调。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "ai/* 分支名"},
                    "workflow": {"type": "string", "default": "ci.yml"},
                    "timeout_seconds": {"type": "integer", "default": 180, "description": "最长等待秒数"},
                },
                "required": ["branch"],
            },
        },
    },
]

# ---------------- dispatcher ----------------

Handler = Callable[[GitHubClient, str, dict], Awaitable[Any]]


def _need(args: dict, key: str) -> Any:
    if key not in args:
        raise ValueError(f"missing required arg: {key}")
    return args[key]


def _check_branch(branch: str) -> None:
    if not branch.startswith("ai/"):
        raise ValueError(f"branch must start with 'ai/'，收到：{branch}")


async def _read_file(gh: GitHubClient, repo: str, args: dict) -> Any:
    data = await gh.read_file(repo, _need(args, "path"), ref=args.get("ref"))
    if data.get("type") != "file":
        return data
    content = data.get("content", "")
    lines = content.splitlines()
    total = len(lines)
    start = args.get("start_line")
    end = args.get("end_line")
    if start or end:
        s = max(1, int(start)) if start else 1
        e = min(total, int(end)) if end else total
        sliced = "\n".join(lines[s - 1 : e])
        return {
            **data,
            "content": sliced,
            "total_lines": total,
            "range": [s, e],
        }
    return {**data, "total_lines": total}


async def _list_dir(gh: GitHubClient, repo: str, args: dict) -> Any:
    return await gh.list_dir(repo, args.get("path", ""), ref=args.get("ref"))


async def _search_code(gh: GitHubClient, repo: str, args: dict) -> Any:
    return await gh.search_code(
        repo, _need(args, "query"), max_results=args.get("max_results", 20)
    )


async def _write_file(gh: GitHubClient, repo: str, args: dict) -> Any:
    _check_branch(_need(args, "branch"))
    return await gh.write_file(
        repo,
        path=_need(args, "path"),
        content=_need(args, "content"),
        message=_need(args, "message"),
        branch=args["branch"],
        sha=args.get("sha"),
    )


async def _write_files(gh: GitHubClient, repo: str, args: dict) -> Any:
    branch = _need(args, "branch")
    _check_branch(branch)
    files = _need(args, "files")
    if not isinstance(files, list) or not files:
        raise ValueError("files 必须是非空数组")
    return await gh.write_files(
        repo,
        branch=branch,
        files=files,
        message=_need(args, "message"),
    )


async def _ensure_branch(gh: GitHubClient, repo: str, args: dict) -> Any:
    _check_branch(_need(args, "branch"))
    sha = await gh.ensure_branch(repo, args["branch"], _need(args, "from_ref"))
    return {"branch": args["branch"], "sha": sha}


async def _open_pr(gh: GitHubClient, repo: str, args: dict) -> Any:
    pr = await gh.open_pr(
        repo,
        title=_need(args, "title"),
        head=_need(args, "head"),
        base=_need(args, "base"),
        body=args.get("body", ""),
    )
    return {"number": pr["number"], "html_url": pr["html_url"], "state": pr["state"]}


async def _dispatch_workflow(gh: GitHubClient, repo: str, args: dict) -> Any:
    await gh.dispatch_workflow(
        repo,
        workflow=_need(args, "workflow"),
        ref=args.get("ref", "main"),
        inputs=args.get("inputs") or {},
    )
    return {"dispatched": args["workflow"]}


async def _list_workflows(gh: GitHubClient, repo: str, args: dict) -> Any:
    wfs = await gh.list_workflows(repo)
    return [{"name": w["name"], "path": w["path"], "state": w["state"]} for w in wfs]


async def _list_runs(gh: GitHubClient, repo: str, args: dict) -> Any:
    runs = await gh.list_runs(repo, workflow=args.get("workflow"), per_page=args.get("per_page", 5))
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "status": r["status"],
            "conclusion": r["conclusion"],
            "head_branch": r["head_branch"],
            "created_at": r["created_at"],
            "html_url": r["html_url"],
        }
        for r in runs
    ]


async def _list_secrets(gh: GitHubClient, repo: str, args: dict) -> Any:
    return await gh.list_secrets(repo)


async def _run_ci(gh: GitHubClient, repo: str, args: dict) -> Any:
    branch = _need(args, "branch")
    _check_branch(branch)
    workflow = args.get("workflow", "ci.yml")
    timeout = int(args.get("timeout_seconds", 180))
    poll_interval = 5

    # 用最新 commit sha 标识"这次"的 run，避免误识别旧 run
    ref = await gh._request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
    head_sha = ref["object"]["sha"]

    logger.info("run_ci: dispatch {} on {}@{}", workflow, branch, head_sha[:7])
    await gh.dispatch_workflow(repo, workflow, ref=branch)

    # 等 run 出现（dispatch 是异步的，需要几秒）
    run_id: int | None = None
    deadline = time.time() + timeout
    while time.time() < deadline and run_id is None:
        await asyncio.sleep(poll_interval)
        runs = await gh.list_runs(
            repo, workflow=workflow, branch=branch, head_sha=head_sha, per_page=1
        )
        if not runs:
            # 兜底：按 branch 找最新
            runs = await gh.list_runs(repo, workflow=workflow, branch=branch, per_page=1)
            if runs and runs[0]["head_sha"] == head_sha:
                run_id = runs[0]["id"]
        else:
            run_id = runs[0]["id"]

    if run_id is None:
        return {
            "started": False,
            "error": "等了 {}s 也没见到 run 出现，可能 dispatch 失败".format(timeout),
        }

    # 轮询 run 状态
    while time.time() < deadline:
        run = await gh.get_run(repo, run_id)
        if run["status"] == "completed":
            break
        await asyncio.sleep(poll_interval)
    else:
        return {
            "started": True,
            "run_id": run_id,
            "url": run["html_url"],
            "timed_out": True,
            "last_status": run["status"],
        }

    conclusion = run["conclusion"]
    if conclusion == "success":
        return {
            "conclusion": "success",
            "run_id": run_id,
            "url": run["html_url"],
            "elapsed_seconds": int(time.time() - (deadline - timeout)),
        }

    # 失败：拉失败 job 的日志末尾
    jobs = await gh.list_run_jobs(repo, run_id)
    failed_summaries: list[dict] = []
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        try:
            logs = await gh.get_job_logs(repo, job["id"])
            tail = "\n".join(logs.splitlines()[-60:])
        except Exception as e:  # noqa: BLE001
            tail = f"(读不到日志: {e})"
        failed_steps = [
            s["name"]
            for s in (job.get("steps") or [])
            if s.get("conclusion") == "failure"
        ]
        failed_summaries.append(
            {
                "job_name": job["name"],
                "failed_steps": failed_steps,
                "logs_tail": tail,
            }
        )

    return {
        "conclusion": conclusion,
        "run_id": run_id,
        "url": run["html_url"],
        "failed_jobs": failed_summaries,
        "hint": "根据 logs_tail 里的 ::error:: 行定位问题，修代码后再 run_ci 一次。",
    }


HANDLERS: dict[str, Handler] = {
    "read_file": _read_file,
    "list_dir": _list_dir,
    "search_code": _search_code,
    "write_file": _write_file,
    "write_files": _write_files,
    "ensure_branch": _ensure_branch,
    "open_pr": _open_pr,
    "dispatch_workflow": _dispatch_workflow,
    "list_workflows": _list_workflows,
    "list_runs": _list_runs,
    "list_secrets": _list_secrets,
    "run_ci": _run_ci,
}


async def dispatch(gh: GitHubClient, repo: str, name: str, args: dict) -> dict:
    """
    执行一个工具调用，统一返回 {ok, result|error} 给 AI。
    所有异常都吞掉转成 error 字符串，让 AI 能自己反思下一步。
    """
    handler = HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"unknown tool: {name}"}

    try:
        result = await handler(gh, repo, args)
        return {"ok": True, "result": result}
    except GitHubError as e:
        logger.warning("tool {} GitHubError: {}", name, e)
        return {"ok": False, "error": str(e)}
    except ValueError as e:
        return {"ok": False, "error": f"bad arguments: {e}"}
    except Exception as e:  # noqa: BLE001
        logger.exception("tool {} unexpected", name)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def tool_result_to_message(call_id: str, name: str, payload: dict) -> dict:
    """构造发回 LLM 的 tool 角色消息。"""
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": name,
        "content": json.dumps(payload, ensure_ascii=False, default=str),
    }
