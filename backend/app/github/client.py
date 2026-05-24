"""
GitHub API 封装层。

设计原则：
- 全异步（httpx.AsyncClient）
- 每个 client 实例对应一个用户 + 一个 token
- 方法粒度对齐 AI 的工具集；返回结构化 dict，调用方不用碰 raw response
- 失败统一抛 GitHubError 子类
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
from loguru import logger
from nacl import encoding, public

from .errors import raise_for

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
ACCEPT = "application/vnd.github+json"
API_VERSION = "2022-11-28"


class GitHubClient:
    def __init__(self, token: str, api_base: str = "https://api.github.com") -> None:
        if not token:
            raise ValueError("GitHub token is required")
        self.api_base = api_base.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.api_base,
            timeout=DEFAULT_TIMEOUT,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": ACCEPT,
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "app-for-oneself/0.1",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ----------------------------- low-level -----------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        accept: str | None = None,
        allow_404: bool = False,
    ) -> Any:
        headers = {"Accept": accept} if accept else None
        resp = await self._client.request(
            method, path, json=json, params=params, headers=headers
        )
        if resp.status_code == 204:
            return None
        if resp.status_code >= 400:
            if resp.status_code == 404 and allow_404:
                return None
            try:
                msg = resp.json().get("message", resp.text)
            except Exception:
                msg = resp.text
            logger.warning(
                "GitHub {} {} -> {} | {}", method, path, resp.status_code, msg
            )
            raise_for(resp.status_code, msg, url=str(resp.request.url))
        if "application/json" in resp.headers.get("content-type", ""):
            return resp.json()
        return resp.content

    # ----------------------------- meta -----------------------------

    async def whoami(self) -> dict:
        return await self._request("GET", "/user")

    async def get_repo(self, repo: str) -> dict:
        return await self._request("GET", f"/repos/{repo}")

    async def create_repo(
        self,
        name: str,
        *,
        private: bool = False,
        description: str = "",
        auto_init: bool = True,
        homepage: str = "",
        org: str | None = None,
    ) -> dict:
        """创建一个仓库（用户名下，或指定 org 下）。"""
        payload = {
            "name": name,
            "private": private,
            "description": description,
            "auto_init": auto_init,
            "homepage": homepage,
        }
        path = f"/orgs/{org}/repos" if org else "/user/repos"
        return await self._request("POST", path, json=payload)

    async def enable_pages(self, repo: str, build_type: str = "workflow") -> dict:
        """启用 GitHub Pages；build_type=workflow 走 Actions（支持任意分支预览）。

        - 若 Pages 已启用：直接返回当前配置（不重新设置 build_type）
        - 若未启用：POST 创建
        """
        existing = await self.get_pages_info(repo)
        if existing:
            return existing
        return await self._request(
            "POST", f"/repos/{repo}/pages", json={"build_type": build_type}
        )

    async def open_environment_branches(self, repo: str, environment: str = "github-pages") -> None:
        """放开 environment 的 deployment branch policy（允许任意分支部署）。"""
        await self._request(
            "PUT",
            f"/repos/{repo}/environments/{environment}",
            json={"deployment_branch_policy": None},
        )

    # ----------------------------- contents -----------------------------

    async def read_file(self, repo: str, path: str, ref: str | None = None) -> dict:
        """
        返回 {path, content, sha, encoding} 或目录列表（list）。
        """
        params = {"ref": ref} if ref else None
        data = await self._request(
            "GET", f"/repos/{repo}/contents/{path}", params=params
        )
        if isinstance(data, list):
            return {"path": path, "type": "dir", "entries": data}
        if data.get("encoding") == "base64":
            raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return {
                "path": data["path"],
                "type": "file",
                "content": raw,
                "sha": data["sha"],
                "size": data["size"],
            }
        return data

    async def write_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> dict:
        """
        创建或更新文件；更新时必须传 sha。
        """
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        return await self._request(
            "PUT", f"/repos/{repo}/contents/{path}", json=payload
        )

    async def write_files(
        self,
        repo: str,
        branch: str,
        files: list[dict],
        message: str,
    ) -> dict:
        """
        通过 Git Data API 在 branch 上提交一个包含多个文件改动的 commit。
        files: [{"path": "...", "content": "...", "mode": "100644" (默认)}, ...]
        - 自动以 branch 当前 head 为 base tree
        - 支持创建新文件 + 更新已有文件
        返回 {commit_sha, branch}
        """
        if not files:
            raise ValueError("files 不能为空")

        # 1. 拿 branch head
        ref_obj = await self._request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        parent_sha = ref_obj["object"]["sha"]
        commit_obj = await self._request(
            "GET", f"/repos/{repo}/git/commits/{parent_sha}"
        )
        base_tree = commit_obj["tree"]["sha"]

        # 2. 为每个文件创建 blob
        tree_entries: list[dict] = []
        for f in files:
            blob = await self._request(
                "POST",
                f"/repos/{repo}/git/blobs",
                json={
                    "content": f["content"],
                    "encoding": "utf-8",
                },
            )
            tree_entries.append(
                {
                    "path": f["path"],
                    "mode": f.get("mode", "100644"),
                    "type": "blob",
                    "sha": blob["sha"],
                }
            )

        # 3. 新 tree
        tree = await self._request(
            "POST",
            f"/repos/{repo}/git/trees",
            json={"base_tree": base_tree, "tree": tree_entries},
        )

        # 4. 新 commit
        commit = await self._request(
            "POST",
            f"/repos/{repo}/git/commits",
            json={"message": message, "tree": tree["sha"], "parents": [parent_sha]},
        )

        # 5. 推 branch
        await self._request(
            "PATCH",
            f"/repos/{repo}/git/refs/heads/{branch}",
            json={"sha": commit["sha"], "force": False},
        )

        return {"commit_sha": commit["sha"], "branch": branch, "files": [f["path"] for f in files]}

    async def list_dir(self, repo: str, path: str = "", ref: str | None = None) -> list[dict]:
        params = {"ref": ref} if ref else None
        data = await self._request(
            "GET", f"/repos/{repo}/contents/{path}", params=params, allow_404=True
        )
        if data is None:
            return []
        if isinstance(data, dict):
            return [data]
        return [
            {"name": e["name"], "type": e["type"], "path": e["path"], "size": e.get("size")}
            for e in data
        ]

    async def search_code(self, repo: str, query: str, max_results: int = 30) -> list[dict]:
        params = {"q": f"{query} repo:{repo}", "per_page": max_results}
        data = await self._request("GET", "/search/code", params=params)
        return [
            {"path": item["path"], "name": item["name"], "sha": item["sha"]}
            for item in data.get("items", [])
        ]

    # ----------------------------- branches & PRs -----------------------------

    async def get_branch(self, repo: str, branch: str) -> dict | None:
        return await self._request(
            "GET", f"/repos/{repo}/branches/{branch}", allow_404=True
        )

    async def create_branch(self, repo: str, branch: str, from_ref: str) -> dict:
        ref = await self._request("GET", f"/repos/{repo}/git/ref/heads/{from_ref}")
        sha = ref["object"]["sha"]
        return await self._request(
            "POST",
            f"/repos/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": sha},
        )

    async def ensure_branch(self, repo: str, branch: str, from_ref: str) -> str:
        existing = await self.get_branch(repo, branch)
        if existing:
            return existing["commit"]["sha"]
        created = await self.create_branch(repo, branch, from_ref)
        return created["object"]["sha"]

    async def open_pr(
        self, repo: str, title: str, head: str, base: str, body: str = ""
    ) -> dict:
        return await self._request(
            "POST",
            f"/repos/{repo}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
        )

    async def merge_pr(self, repo: str, number: int, method: str = "squash") -> dict:
        return await self._request(
            "PUT",
            f"/repos/{repo}/pulls/{number}/merge",
            json={"merge_method": method},
        )

    async def close_pr(self, repo: str, number: int) -> dict:
        return await self._request(
            "PATCH",
            f"/repos/{repo}/pulls/{number}",
            json={"state": "closed"},
        )

    async def delete_branch(self, repo: str, branch: str) -> None:
        await self._request("DELETE", f"/repos/{repo}/git/refs/heads/{branch}")

    # ----------------------------- workflows -----------------------------

    async def list_workflows(self, repo: str) -> list[dict]:
        data = await self._request("GET", f"/repos/{repo}/actions/workflows")
        return data.get("workflows", [])

    async def dispatch_workflow(
        self, repo: str, workflow: str, ref: str = "main", inputs: dict | None = None
    ) -> None:
        await self._request(
            "POST",
            f"/repos/{repo}/actions/workflows/{workflow}/dispatches",
            json={"ref": ref, "inputs": inputs or {}},
        )

    async def list_runs(
        self,
        repo: str,
        workflow: str | None = None,
        per_page: int = 10,
        branch: str | None = None,
        head_sha: str | None = None,
    ) -> list[dict]:
        path = (
            f"/repos/{repo}/actions/workflows/{workflow}/runs"
            if workflow
            else f"/repos/{repo}/actions/runs"
        )
        params: dict = {"per_page": per_page}
        if branch:
            params["branch"] = branch
        if head_sha:
            params["head_sha"] = head_sha
        data = await self._request("GET", path, params=params)
        return data.get("workflow_runs", [])

    async def get_run(self, repo: str, run_id: int) -> dict:
        return await self._request("GET", f"/repos/{repo}/actions/runs/{run_id}")

    async def get_run_logs(self, repo: str, run_id: int) -> bytes:
        """返回 zip 压缩的日志；调用方按需解压。"""
        return await self._request(
            "GET",
            f"/repos/{repo}/actions/runs/{run_id}/logs",
            accept="application/zip",
        )

    async def list_run_jobs(self, repo: str, run_id: int) -> list[dict]:
        data = await self._request(
            "GET", f"/repos/{repo}/actions/runs/{run_id}/jobs"
        )
        return data.get("jobs", [])

    async def get_job_logs(self, repo: str, job_id: int) -> str:
        """单个 job 的纯文本日志（不是 zip）。"""
        data = await self._request(
            "GET",
            f"/repos/{repo}/actions/jobs/{job_id}/logs",
            accept="text/plain",
        )
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)

    # ----------------------------- pages -----------------------------

    async def get_pages_info(self, repo: str) -> dict | None:
        """返回 Pages 配置；未启用返回 None。"""
        return await self._request("GET", f"/repos/{repo}/pages", allow_404=True)

    # ----------------------------- merge -----------------------------

    async def fast_forward_merge(self, repo: str, base: str, head: str) -> dict:
        """
        把 base 分支前进到 head 的 sha（fast-forward）。
        - 若 base 不是 head 的祖先，GitHub 会返回 422，需要先 rebase。
        """
        head_ref = await self._request("GET", f"/repos/{repo}/git/ref/heads/{head}")
        head_sha = head_ref["object"]["sha"]
        return await self._request(
            "PATCH",
            f"/repos/{repo}/git/refs/heads/{base}",
            json={"sha": head_sha, "force": False},
        )

    async def merge_branch(self, repo: str, base: str, head: str, message: str | None = None) -> dict:
        """普通 merge（生成 merge commit），用于 base 已偏离的兜底场景。"""
        payload: dict = {"base": base, "head": head}
        if message:
            payload["commit_message"] = message
        return await self._request("POST", f"/repos/{repo}/merges", json=payload)

    # ----------------------------- secrets -----------------------------

    async def _repo_public_key(self, repo: str) -> dict:
        return await self._request("GET", f"/repos/{repo}/actions/secrets/public-key")

    async def list_secrets(self, repo: str) -> list[dict]:
        data = await self._request("GET", f"/repos/{repo}/actions/secrets")
        return [
            {"name": s["name"], "updated_at": s["updated_at"]}
            for s in data.get("secrets", [])
        ]

    async def set_secret(self, repo: str, name: str, value: str) -> None:
        pk = await self._repo_public_key(repo)
        encrypted = _encrypt_secret(pk["key"], value)
        await self._request(
            "PUT",
            f"/repos/{repo}/actions/secrets/{name}",
            json={"encrypted_value": encrypted, "key_id": pk["key_id"]},
        )

    async def delete_secret(self, repo: str, name: str) -> None:
        await self._request("DELETE", f"/repos/{repo}/actions/secrets/{name}")

    # variables（非加密）
    async def list_variables(self, repo: str) -> list[dict]:
        data = await self._request("GET", f"/repos/{repo}/actions/variables")
        return data.get("variables", [])

    async def set_variable(self, repo: str, name: str, value: str) -> None:
        existing = await self._request(
            "GET", f"/repos/{repo}/actions/variables/{name}", allow_404=True
        )
        if existing:
            await self._request(
                "PATCH",
                f"/repos/{repo}/actions/variables/{name}",
                json={"name": name, "value": value},
            )
        else:
            await self._request(
                "POST",
                f"/repos/{repo}/actions/variables",
                json={"name": name, "value": value},
            )

    async def delete_variable(self, repo: str, name: str) -> None:
        await self._request("DELETE", f"/repos/{repo}/actions/variables/{name}")


def _encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """libsodium sealed box，GitHub Secrets 必需。"""
    pk = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")
