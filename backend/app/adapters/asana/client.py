from __future__ import annotations

import asyncio
import os
import random

import httpx
from dotenv import load_dotenv

load_dotenv()

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class AsanaClient:
    def __init__(
        self,
        pat: str | None = None,
        base_url: str = "https://app.asana.com/api/1.0",
        timeout: float = 30.0,
    ) -> None:
        self.pat = pat or os.getenv("ASANA_PAT")
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.pat:
            headers["Authorization"] = f"Bearer {self.pat}"
        return headers

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsanaClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def get(self, path: str, params: dict | None = None) -> dict:
        return await self._request("GET", path, params=params)

    async def post(
        self,
        path: str,
        json: dict | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict:
        return await self._request("POST", path, json=json, idempotency_key=idempotency_key)

    async def put(
        self,
        path: str,
        json: dict | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict:
        return await self._request("PUT", path, json=json, idempotency_key=idempotency_key)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        headers: dict[str, str] = {}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(4):
            response = await self._client.request(
                method, path, params=params, json=json, headers=headers or None,
            )
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                response.raise_for_status()
                return response.json()

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "1"))
            else:
                # 5xx: exponential backoff starting at 1s
                retry_after = 2.0 ** attempt

            if attempt == 3:
                response.raise_for_status()

            # Add jitter: 0–1s random offset to avoid thundering herd
            await asyncio.sleep(retry_after + random.uniform(0, 1))

        raise NotImplementedError("Asana client request retry loop exhausted unexpectedly.")

    async def check(self) -> bool:
        if not self.pat:
            return False
        await self.get("/users/me")
        return True
