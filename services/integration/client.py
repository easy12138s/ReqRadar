"""HTTP 客户端 — 封装对下游服务的调用。"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0


class ServiceClient:
    """下游服务 HTTP 客户端。"""

    def __init__(self) -> None:
        self._internal_key = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")
        self._cognitive_rt_url = os.environ.get("COGNITIVE_RT_URL", "http://localhost:8002")
        self._index_url = os.environ.get("INDEX_SERVICE_URL", "http://localhost:8003")
        self._output_url = os.environ.get("OUTPUT_SERVICE_URL", "http://localhost:8004")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=_DEFAULT_TIMEOUT,
                headers={"X-Internal-API-Key": self._internal_key},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Cognitive-RT ──────────────────────────────────
    async def get_sessions(
        self, project_id: str, status: str | None = None, limit: int = 20
    ) -> dict:
        client = await self._get_client()
        params: dict = {"project_id": project_id, "limit": limit}
        if status:
            params["status"] = status
        resp = await client.get(f"{self._cognitive_rt_url}/internal/v2/sessions", params=params)
        return resp.json()

    async def get_session_detail(self, session_id: str) -> dict:
        client = await self._get_client()
        resp = await client.get(f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}")
        return resp.json()

    async def get_evidence(
        self, session_id: str, evidence_type: str | None = None, limit: int = 50
    ) -> dict:
        client = await self._get_client()
        params: dict = {"limit": limit}
        if evidence_type:
            params["type"] = evidence_type
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/evidence", params=params
        )
        return resp.json()

    # ── Index Service ─────────────────────────────────
    async def query_memory(
        self, project_id: str, query: str, knowledge_types: str | None = None, top_k: int = 10
    ) -> dict:
        client = await self._get_client()
        body = {"project_id": project_id, "query": query, "top_k": top_k}
        if knowledge_types:
            body["knowledge_types"] = knowledge_types
        resp = await client.post(f"{self._index_url}/internal/v2/knowledge/query", json=body)
        return resp.json()

    # ── Output Service ────────────────────────────────
    async def get_latest_report(self, session_id: str) -> dict:
        client = await self._get_client()
        resp = await client.get(f"{self._output_url}/internal/v2/reports/{session_id}/latest")
        return resp.json()
