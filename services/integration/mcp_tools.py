"""MCP 工具定义 — 7 个 V2 MCP 工具，通过 ServiceClient 调用下游。"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def register_tools(mcp_server, service_client, audit_log, key_manager) -> None:
    """在 FastMCP 实例上注册所有 MCP 工具。"""

    @mcp_server.tool()
    async def search_requirements(
        project_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """搜索项目需求。按关键词在项目需求文档中语义检索。"""
        start = time.monotonic()
        try:
            result = await service_client.query_memory(project_id, query, top_k=limit)
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="search_requirements",
                arguments={"project_id": project_id, "query": query, "limit": limit},
                result_summary=f"Found {len(result.get('items', []))} results",
                duration_ms=duration_ms,
            )
            return result.get("items", [])
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="search_requirements",
                arguments={"project_id": project_id, "query": query, "limit": limit},
                result_summary="error",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            return [{"error": f"搜索失败: {e}"}]

    @mcp_server.tool()
    async def get_session_detail(
        session_id: str,
    ) -> dict | str:
        """获取分析 Session 的详细信息，包括状态、进度、配置。"""
        start = time.monotonic()
        try:
            result = await service_client.get_session_detail(session_id)
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="get_session_detail",
                arguments={"session_id": session_id},
                result_summary="Found" if result else "Not found",
                duration_ms=duration_ms,
            )
            return result
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="get_session_detail",
                arguments={"session_id": session_id},
                result_summary="error",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            return f"Session 查询失败: {e}"

    @mcp_server.tool()
    async def get_project_knowledge(
        project_id: str,
        knowledge_types: str | None = None,
        topics: str | None = None,
    ) -> dict | str:
        """获取项目的持久化知识库，包括术语表、模块画像、架构约束、决策记录等。"""
        start = time.monotonic()
        try:
            result = await service_client.query_memory(
                project_id,
                query=topics or "project knowledge",
                knowledge_types=knowledge_types,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="get_project_knowledge",
                arguments={
                    "project_id": project_id,
                    "knowledge_types": knowledge_types,
                    "topics": topics,
                },
                result_summary=f"Found {len(result.get('items', []))} items",
                duration_ms=duration_ms,
            )
            return result
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="get_project_knowledge",
                arguments={"project_id": project_id, "knowledge_types": knowledge_types},
                result_summary="error",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            return f"知识查询失败: {e}"

    @mcp_server.tool()
    async def read_report(
        session_id: str,
    ) -> dict | str:
        """读取指定 Session 的最新分析报告。"""
        start = time.monotonic()
        try:
            result = await service_client.get_latest_report(session_id)
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="read_report",
                arguments={"session_id": session_id},
                result_summary="Found" if result.get("output_uri") else "No report",
                duration_ms=duration_ms,
            )
            return result
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="read_report",
                arguments={"session_id": session_id},
                result_summary="error",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            return f"报告读取失败: {e}"

    @mcp_server.tool()
    async def list_sessions(
        project_id: str,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """列出项目的分析 Session 列表，可按状态过滤。"""
        start = time.monotonic()
        try:
            result = await service_client.get_sessions(project_id, status=status, limit=limit)
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="list_sessions",
                arguments={"project_id": project_id, "status": status, "limit": limit},
                result_summary=f"Found {len(result.get('sessions', []))} sessions",
                duration_ms=duration_ms,
            )
            return result.get("sessions", [])
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="list_sessions",
                arguments={"project_id": project_id, "status": status, "limit": limit},
                result_summary="error",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            return [{"error": f"Session 列表查询失败: {e}"}]

    @mcp_server.tool()
    async def search_knowledge(
        project_id: str,
        query: str,
        knowledge_types: list[str] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """语义检索项目的 L3 持久化知识。支持按知识类型过滤。"""
        start = time.monotonic()
        try:
            types_str = ",".join(knowledge_types) if knowledge_types else None
            result = await service_client.query_memory(
                project_id,
                query=query,
                knowledge_types=types_str,
                top_k=top_k,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="search_knowledge",
                arguments={
                    "project_id": project_id,
                    "query": query,
                    "knowledge_types": knowledge_types,
                    "top_k": top_k,
                },
                result_summary=f"Found {len(result.get('items', []))} results",
                duration_ms=duration_ms,
            )
            return result.get("items", [])
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="search_knowledge",
                arguments={"project_id": project_id, "query": query},
                result_summary="error",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            return [{"error": f"知识检索失败: {e}"}]

    @mcp_server.tool()
    async def get_evidence(
        session_id: str,
        evidence_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """获取分析 Session 中收集的证据列表。可按证据类型过滤。"""
        start = time.monotonic()
        try:
            result = await service_client.get_evidence(
                session_id, evidence_type=evidence_type, limit=limit
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="get_evidence",
                arguments={
                    "session_id": session_id,
                    "evidence_type": evidence_type,
                    "limit": limit,
                },
                result_summary=f"Found {len(result.get('items', []))} evidence",
                duration_ms=duration_ms,
            )
            return result.get("items", [])
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            audit_log.record(
                tool_name="get_evidence",
                arguments={"session_id": session_id, "evidence_type": evidence_type},
                result_summary="error",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            return [{"error": f"证据查询失败: {e}"}]
