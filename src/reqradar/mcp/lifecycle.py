import asyncio
import contextlib
import logging

from fastmcp import FastMCP

from reqradar.mcp.context import MCPRuntimeContext
from reqradar.mcp.tools import register_tools, set_context

logger = logging.getLogger("reqradar.mcp.lifecycle")


class MCPServerHandle:
    """Handle for a running MCP server."""

    def __init__(self, mcp: FastMCP, task: asyncio.Task | None = None):
        self.mcp = mcp
        self.task = task
        self.started = False


def create_mcp_server(ctx: MCPRuntimeContext) -> FastMCP:
    """Create and configure a FastMCP server with tools registered."""
    mcp = FastMCP(
        "reqradar",
        instructions=(
            "ReqRadar MCP Server — Query published requirement releases, "
            "analysis reports, and project memory. All tools are read-only."
        ),
    )
    set_context(ctx)
    register_tools(mcp)
    return mcp


async def start_mcp_server(ctx: MCPRuntimeContext) -> MCPServerHandle:
    """Start the MCP server as a background asyncio task using Streamable HTTP transport."""
    mcp = create_mcp_server(ctx)
    config = ctx.config.mcp

    async def _run():
        try:
            await mcp.run_http_async(
                host=config.host,
                port=config.port,
                path=config.path,
                show_banner=False,
            )
        except OSError as e:
            if "Address already in use" in str(e) or "EADDRINUSE" in str(e):
                logger.error("MCP server port %d already in use — not starting", config.port)
            else:
                raise
        except Exception:
            logger.exception("MCP server failed")

    task = asyncio.create_task(_run())
    handle = MCPServerHandle(mcp=mcp, task=task)
    handle.started = True
    logger.info(
        "MCP server started on %s:%d%s",
        config.host,
        config.port,
        config.path,
    )
    return handle


async def maybe_start_mcp_with_web(app) -> None:
    """Start MCP server alongside the web app if configured."""
    existing = getattr(app.state, "mcp_handle", None)
    if existing is not None and existing.started:
        logger.warning("MCP server already started — skipping duplicate start")
        return

    config = getattr(app.state, "config", None)
    if config is None or not config.mcp.enabled or not config.mcp.auto_start_with_web:
        return

    from reqradar.mcp.context import MCPRuntimeContext

    ctx = MCPRuntimeContext(
        config=config,
        session_factory=app.state.session_factory,
        paths=app.state.paths,
        report_storage=app.state.report_storage,
    )
    handle = await start_mcp_server(ctx)
    app.state.mcp_handle = handle


async def stop_mcp_with_web(app) -> None:
    """Stop the MCP server when the web app shuts down."""
    handle = getattr(app.state, "mcp_handle", None)
    if handle is None:
        return
    if handle.task and not handle.task.done():
        handle.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await handle.task
    handle.started = False
    app.state.mcp_handle = None
    logger.info("MCP server stopped")
