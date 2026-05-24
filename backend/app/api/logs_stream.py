"""Workflow 日志实时流：增量轮询 GitHub jobs/logs API → SSE 推送给前端。"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from ..github.client import GitHubClient
from ..github.errors import GitHubError
from .deps import github_client, require_repo

router = APIRouter(prefix="/api/runs", tags=["logs"])

POLL_INTERVAL = 2.0  # 秒
MAX_DURATION = 600  # 单流最长 10 分钟


@router.get("/{run_id}/stream")
async def stream_run_logs(
    run_id: int,
    repo: str = Depends(require_repo),
    gh: GitHubClient = Depends(github_client),
):
    """实时拉日志。完成后流终止。"""
    # 先确认 run 存在
    try:
        run = await gh.get_run(repo, run_id)
    except GitHubError as e:
        raise HTTPException(e.status, e.message)

    async def stream():
        def evt(name: str, data: dict):
            return {"event": name, "data": json.dumps(data, ensure_ascii=False, default=str)}

        # 推初始状态
        yield evt("status", {
            "status": run["status"], "conclusion": run["conclusion"],
            "name": run["name"], "head_branch": run["head_branch"],
            "html_url": run["html_url"],
        })

        # 跟踪每个 job 已发送的字节偏移量（用于增量）
        job_offsets: dict[int, int] = {}
        deadline = asyncio.get_event_loop().time() + MAX_DURATION
        last_status = run["status"]
        last_conclusion = run.get("conclusion")

        while asyncio.get_event_loop().time() < deadline:
            try:
                current = await gh.get_run(repo, run_id)
            except GitHubError as e:
                yield evt("error", {"message": str(e)})
                return

            # 状态变化推一下
            if current["status"] != last_status or current.get("conclusion") != last_conclusion:
                last_status = current["status"]
                last_conclusion = current.get("conclusion")
                yield evt("status", {
                    "status": last_status, "conclusion": last_conclusion,
                })

            # 拉每个 job 的日志增量
            try:
                jobs = await gh.list_run_jobs(repo, run_id)
            except GitHubError as e:
                yield evt("error", {"message": str(e)})
                return

            for job in jobs:
                job_id = job["id"]
                # 只在 job 已经开始（in_progress 或 completed）时拉日志
                if job.get("status") == "queued":
                    continue
                try:
                    logs = await gh.get_job_logs(repo, job_id)
                except GitHubError:
                    continue

                prev_len = job_offsets.get(job_id, 0)
                if len(logs) > prev_len:
                    chunk = logs[prev_len:]
                    job_offsets[job_id] = len(logs)
                    yield evt("log", {
                        "job_id": job_id,
                        "job_name": job["name"],
                        "job_status": job.get("status"),
                        "job_conclusion": job.get("conclusion"),
                        "chunk": chunk,
                    })

            # Run 完成 → 结束流
            if current["status"] == "completed":
                yield evt("done", {
                    "status": "completed",
                    "conclusion": current.get("conclusion"),
                    "html_url": current["html_url"],
                })
                return

            await asyncio.sleep(POLL_INTERVAL)

        # 超时
        yield evt("timeout", {"message": f"日志流超过最大时长 {MAX_DURATION}s 自动断开"})

    return EventSourceResponse(stream())
