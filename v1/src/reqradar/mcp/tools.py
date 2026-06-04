import logging
import time

from reqradar.mcp.context import MCPRuntimeContext

logger = logging.getLogger("reqradar.mcp.tools")

_ctx: MCPRuntimeContext | None = None


def set_context(ctx: MCPRuntimeContext) -> None:
    global _ctx
    _ctx = ctx


def register_tools(mcp_server) -> None:
    """Register all MCP tools on the given FastMCP server instance."""

    @mcp_server.tool()
    async def search_published_requirements(
        project_id: int | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search published requirement releases. Use this to find requirements by keyword or project."""
        if _ctx is None:
            return [{"error": "MCP server context not initialized"}]
        results = await _ctx.content_reader.search_published_requirements(
            project_id=project_id, query=query, limit=limit
        )
        if _ctx.config.mcp.audit_enabled:
            async with _ctx.session_factory() as audit_db:
                from reqradar.web.services.mcp_audit_service import record_call

                await record_call(
                    audit_db,
                    access_key_id=None,
                    tool_name="search_published_requirements",
                    arguments={"project_id": project_id, "query": query, "limit": limit},
                    result_summary=f"Found {len(results)} releases",
                    duration_ms=0,
                )
        return results

    @mcp_server.tool()
    async def get_requirement_context(
        release_id: int,
    ) -> dict | str:
        """Get full context for a published requirement release by ID. Returns content, context_json, and metadata."""
        if _ctx is None:
            return "MCP server context not initialized"
        start = time.monotonic()
        result = await _ctx.content_reader.get_requirement_context(release_id)
        duration_ms = int((time.monotonic() - start) * 1000)
        if _ctx.config.mcp.audit_enabled:
            async with _ctx.session_factory() as audit_db:
                from reqradar.web.services.mcp_audit_service import record_call

                await record_call(
                    audit_db,
                    access_key_id=None,
                    tool_name="get_requirement_context",
                    arguments={"release_id": release_id},
                    result_summary="Found" if result else "Not found",
                    duration_ms=duration_ms,
                )
        if result is None:
            return f"Published requirement release {release_id} not found"
        return result

    @mcp_server.tool()
    async def get_project_memory(
        project_id: int,
    ) -> dict | str:
        """Get project memory/context including tech stack, modules, terminology, and constraints."""
        if _ctx is None:
            return "MCP server context not initialized"
        start = time.monotonic()
        result = await _ctx.content_reader.read_project_memory(project_id)
        duration_ms = int((time.monotonic() - start) * 1000)
        if _ctx.config.mcp.audit_enabled:
            async with _ctx.session_factory() as audit_db:
                from reqradar.web.services.mcp_audit_service import record_call

                await record_call(
                    audit_db,
                    access_key_id=None,
                    tool_name="get_project_memory",
                    arguments={"project_id": project_id},
                    result_summary="Found" if result else "Not found",
                    duration_ms=duration_ms,
                )
        if result is None:
            return f"Project memory for project {project_id} not found"
        return result

    @mcp_server.tool()
    async def read_report(
        task_id: int,
        version: int | None = None,
    ) -> dict | str:
        """Read the analysis report for a task. Returns markdown content. Optionally specify a version number."""
        if _ctx is None:
            return "MCP server context not initialized"
        start = time.monotonic()
        md = await _ctx.content_reader.read_report_markdown(task_id, version=version)
        duration_ms = int((time.monotonic() - start) * 1000)
        if _ctx.config.mcp.audit_enabled:
            async with _ctx.session_factory() as audit_db:
                from reqradar.web.services.mcp_audit_service import record_call

                await record_call(
                    audit_db,
                    access_key_id=None,
                    tool_name="read_report",
                    arguments={"task_id": task_id, "version": version},
                    result_summary="Found" if md else "Not found",
                    duration_ms=duration_ms,
                )
        if md is None:
            return f"Report for task {task_id} not found"
        return {"task_id": task_id, "markdown": md, "version": version}

    @mcp_server.tool()
    async def list_analyses(
        project_id: int,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict] | str:
        """List analysis tasks for a project. Optionally filter by status."""
        if _ctx is None:
            return "MCP server context not initialized"
        start = time.monotonic()
        results = await _ctx.content_reader.list_analyses(
            project_id=project_id, status=status, limit=limit
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        if _ctx.config.mcp.audit_enabled:
            async with _ctx.session_factory() as audit_db:
                from reqradar.web.services.mcp_audit_service import record_call

                await record_call(
                    audit_db,
                    access_key_id=None,
                    tool_name="list_analyses",
                    arguments={"project_id": project_id, "status": status, "limit": limit},
                    result_summary=f"Found {len(results)} analyses",
                    duration_ms=duration_ms,
                )
        return results
