"""HTTP 客户端 — 封装对下游服务的调用。"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_REPORT_TIMEOUT = 120.0


class ServiceClient:
    """下游服务 HTTP 客户端。"""

    def __init__(self) -> None:
        self._internal_key = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")
        self._auth_url = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8001")
        self._cognitive_rt_url = os.environ.get("COGNITIVE_RT_URL", "http://localhost:8002")
        self._index_url = os.environ.get("INDEX_SERVICE_URL", "http://localhost:8003")
        self._output_url = os.environ.get("OUTPUT_SERVICE_URL", "http://localhost:8004")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端单例。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=_DEFAULT_TIMEOUT,
                headers={"X-Internal-API-Key": self._internal_key},
            )
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端连接。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _headers(self, jwt_token: str | None = None) -> dict[str, str]:
        """构建请求头，注入内部 API Key 和可选的 JWT。"""
        h: dict[str, str] = {"X-Internal-API-Key": self._internal_key}
        if jwt_token:
            h["Authorization"] = f"Bearer {jwt_token}"
        return h

    # ── Auth Service ──────────────────────────────────

    async def verify_token(self, token: str) -> dict:
        """验证 JWT Token。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._auth_url}/internal/v2/auth/verify",
            json={"token": token},
            headers=self._headers(),
        )
        return resp.json()

    # ── Cognitive-RT ──────────────────────────────────

    async def create_session(
        self,
        project_id: str,
        config: dict | None,
        jwt: str | None = None,
    ) -> dict:
        """创建认知会话。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._cognitive_rt_url}/internal/v2/sessions",
            json={"project_id": project_id, "config": config or {}},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_session(self, session_id: str, jwt: str | None = None) -> dict:
        """查询会话状态。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}",
            headers=self._headers(jwt),
        )
        return resp.json()

    async def start_session(
        self,
        session_id: str,
        resume_from: int | None,
        jwt: str | None = None,
    ) -> dict:
        """启动或恢复会话。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/start",
            json={"resume_from": resume_from},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def cancel_session(self, session_id: str, jwt: str | None = None) -> dict:
        """取消会话。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/cancel",
            headers=self._headers(jwt),
        )
        return resp.json()

    async def create_checkpoint(self, session_id: str, jwt: str | None = None) -> dict:
        """手动触发检查点。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/checkpoint",
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_events(
        self,
        session_id: str,
        params: dict | None = None,
        jwt: str | None = None,
    ) -> dict:
        """查询会话事件流。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/events",
            params=params or {},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_trace(
        self,
        session_id: str,
        params: dict | None = None,
        jwt: str | None = None,
    ) -> dict:
        """查询推理链 Trace。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/trace",
            params=params or {},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_evidence(
        self,
        session_id: str,
        params: dict | None = None,
        jwt: str | None = None,
    ) -> dict:
        """查询会话证据列表。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/evidence",
            params=params or {},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_evidence_detail(
        self,
        session_id: str,
        evidence_id: str,
        jwt: str | None = None,
    ) -> dict:
        """查询单条证据详情。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/evidence/{evidence_id}",
            headers=self._headers(jwt),
        )
        return resp.json()

    async def verify_evidence(
        self,
        session_id: str,
        evidence_id: str,
        verified_by: str,
        jwt: str | None = None,
    ) -> dict:
        """验证证据。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/evidence/{evidence_id}/verify",
            json={"verified_by": verified_by},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_dimensions(self, session_id: str, jwt: str | None = None) -> dict:
        """查询维度评估状态。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/dimensions",
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_checkpoints(
        self,
        session_id: str,
        params: dict | None = None,
        jwt: str | None = None,
    ) -> dict:
        """查询检查点版本链。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/checkpoints",
            params=params or {},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_checkpoint_version(
        self,
        session_id: str,
        version: int,
        jwt: str | None = None,
    ) -> dict:
        """查询特定版本检查点。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/checkpoints/{version}",
            headers=self._headers(jwt),
        )
        return resp.json()

    async def restore_checkpoint(
        self,
        session_id: str,
        version: int,
        jwt: str | None = None,
    ) -> dict:
        """从检查点恢复。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._cognitive_rt_url}/internal/v2/sessions/{session_id}/checkpoints/{version}/restore",
            headers=self._headers(jwt),
        )
        return resp.json()

    # ── Index Service ─────────────────────────────────

    async def get_knowledge(
        self,
        project_id: str,
        params: dict | None = None,
        jwt: str | None = None,
    ) -> dict:
        """按项目聚合查询知识。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._index_url}/internal/v2/projects/{project_id}/knowledge",
            params=params or {},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def search_knowledge(
        self,
        project_id: str,
        body: dict,
        jwt: str | None = None,
    ) -> dict:
        """语义检索知识。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._index_url}/internal/v2/projects/{project_id}/knowledge",
            json=body,
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_knowledge_detail(
        self,
        project_id: str,
        kid: str,
        params: dict | None = None,
        jwt: str | None = None,
    ) -> dict:
        """查询单条知识详情。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._index_url}/internal/v2/projects/{project_id}/knowledge/{kid}",
            params=params or {},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def update_knowledge(
        self,
        project_id: str,
        kid: str,
        body: dict,
        jwt: str | None = None,
    ) -> dict:
        """更新知识。"""
        client = await self._get_client()
        resp = await client.put(
            f"{self._index_url}/internal/v2/projects/{project_id}/knowledge/{kid}",
            json=body,
            headers=self._headers(jwt),
        )
        return resp.json()

    async def deprecate_knowledge(
        self,
        project_id: str,
        kid: str,
        body: dict,
        jwt: str | None = None,
    ) -> dict:
        """废弃知识。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._index_url}/internal/v2/projects/{project_id}/knowledge/{kid}/deprecate",
            json=body,
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_knowledge_changelog(
        self,
        project_id: str,
        params: dict | None = None,
        jwt: str | None = None,
    ) -> dict:
        """查询知识变更日志。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._index_url}/internal/v2/projects/{project_id}/knowledge/changelog",
            params=params or {},
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_graph_neighbors(
        self,
        project_id: str,
        params: dict,
        jwt: str | None = None,
    ) -> dict:
        """查询图节点邻居。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._index_url}/internal/v2/projects/{project_id}/graph/neighbors",
            params=params,
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_graph_path(
        self,
        project_id: str,
        params: dict,
        jwt: str | None = None,
    ) -> dict:
        """查询图两节点间路径。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._index_url}/internal/v2/projects/{project_id}/graph/path",
            params=params,
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_graph_subgraph(
        self,
        project_id: str,
        params: dict | None = None,
        jwt: str | None = None,
    ) -> dict:
        """查询子图。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._index_url}/internal/v2/projects/{project_id}/graph/subgraph",
            params=params or {},
            headers=self._headers(jwt),
        )
        return resp.json()

    # ── Output Service ────────────────────────────────

    async def generate_report(
        self,
        session_id: str,
        template_id: str | None,
        output_format: str,
        jwt: str | None = None,
    ) -> dict:
        """请求生成报告。"""
        client = await self._get_client()
        resp = await client.post(
            f"{self._output_url}/internal/v2/reports/generate",
            json={
                "session_id": session_id,
                "template_id": template_id,
                "output_format": output_format,
            },
            timeout=_REPORT_TIMEOUT,
            headers=self._headers(jwt),
        )
        return resp.json()

    async def get_report_status(self, task_id: str, jwt: str | None = None) -> dict:
        """查询报告生成状态。"""
        client = await self._get_client()
        resp = await client.get(
            f"{self._output_url}/internal/v2/reports/{task_id}/status",
            headers=self._headers(jwt),
        )
        return resp.json()
