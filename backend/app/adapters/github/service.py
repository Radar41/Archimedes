from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

_RETRYABLE_SERVER_CODES = {500, 502, 503}


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://api.github.com",
        timeout: float = 30.0,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def get(self, path: str, params: dict | None = None) -> dict:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict | None = None) -> dict:
        return await self._request("POST", path, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        for attempt in range(4):
            response = await self._client.request(method, path, params=params, json=json)

            if self._is_rate_limited(response):
                delay = self._rate_limit_delay(response)
            elif response.status_code in _RETRYABLE_SERVER_CODES:
                delay = 2.0 ** attempt
            else:
                response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()

            if attempt == 3:
                response.raise_for_status()
            # Add jitter to avoid thundering herd
            await asyncio.sleep(delay + random.uniform(0, 1))

        raise NotImplementedError("GitHub client request retry loop exhausted unexpectedly.")

    def _is_rate_limited(self, response: httpx.Response) -> bool:
        if response.status_code == 429:
            return True
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            return True
        return False

    def _rate_limit_delay(self, response: httpx.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            return max(1.0, float(retry_after))

        reset_at = response.headers.get("X-RateLimit-Reset")
        if reset_at is not None:
            return max(1.0, float(reset_at) - time.time())

        return 1.0


async def create_branch(
    repository: str,
    branch_name: str,
    source_sha: str,
    *,
    client: GitHubClient | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    client = client or GitHubClient()
    try:
        return await client.post(
            f"/repos/{repository}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": source_sha},
        )
    finally:
        if owns_client:
            await client.close()


async def create_pr(
    repository: str,
    title: str,
    body: str,
    head: str,
    base: str,
    *,
    client: GitHubClient | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    client = client or GitHubClient()
    try:
        return await client.post(
            f"/repos/{repository}/pulls",
            json={"title": title, "body": body, "head": head, "base": base},
        )
    finally:
        if owns_client:
            await client.close()


async def get_pr_status(
    repository: str,
    pr_number: int,
    *,
    client: GitHubClient | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    client = client or GitHubClient()
    try:
        pr = await client.get(f"/repos/{repository}/pulls/{pr_number}")
        commit_status = await client.get(f"/repos/{repository}/commits/{pr['head']['sha']}/status")
        return {
            "pr_number": pr["number"],
            "state": pr["state"],
            "draft": pr.get("draft", False),
            "mergeable": pr.get("mergeable"),
            "head_sha": pr["head"]["sha"],
            "checks_state": commit_status.get("state"),
            "statuses": commit_status.get("statuses", []),
            "html_url": pr.get("html_url"),
        }
    finally:
        if owns_client:
            await client.close()


async def post_comment(
    repository: str,
    issue_number: int,
    body: str,
    *,
    client: GitHubClient | None = None,
) -> dict[str, Any]:
    owns_client = client is None
    client = client or GitHubClient()
    try:
        return await client.post(
            f"/repos/{repository}/issues/{issue_number}/comments",
            json={"body": body},
        )
    finally:
        if owns_client:
            await client.close()
