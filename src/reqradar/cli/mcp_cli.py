import asyncio
import contextlib

import click

from reqradar.cli.main import cli


@cli.group()
@click.pass_context
def mcp(ctx):
    """MCP server management"""


@mcp.command()
@click.option("--host", default=None, help="Bind host (overrides config)")
@click.option("--port", default=None, type=int, help="Bind port (overrides config)")
@click.option("--no-audit", is_flag=True, default=False, help="Disable audit logging")
@click.pass_context
def serve(ctx, host, port, no_audit):
    """Start the MCP server manually"""
    from reqradar.infrastructure.paths import ensure_dirs, get_paths
    from reqradar.mcp.context import MCPRuntimeContext
    from reqradar.mcp.lifecycle import start_mcp_server
    from reqradar.web.database import create_engine, create_session_factory
    from reqradar.web.services.report_storage import ReportStorage

    config = ctx.obj["config"]
    mcp_config = config.mcp

    if not mcp_config.enabled:
        click.echo(
            "MCP server is not enabled. Set mcp.enabled=true in config or use --host/--port."
        )
        if not host and not port:
            raise SystemExit(1)

    if host:
        mcp_config.host = host
    if port:
        mcp_config.port = port
    if no_audit:
        mcp_config.audit_enabled = False

    paths = get_paths(config)
    ensure_dirs(paths)

    from reqradar.infrastructure.paths import derive_database_url

    database_url = derive_database_url(config)
    report_storage = ReportStorage(paths["reports"])

    engine = create_engine(database_url)
    session_factory = create_session_factory(engine)

    ctx_obj = MCPRuntimeContext(
        config=config,
        session_factory=session_factory,
        paths=paths,
        report_storage=report_storage,
    )

    from reqradar.web.services.mcp_auth_service import build_mcp_public_url

    mcp_url = build_mcp_public_url(mcp_config)

    click.echo("")
    click.echo("\033[36m\033[1m ReqRadar MCP Server\033[0m")
    click.echo(f" Endpoint: {mcp_url}")
    click.echo(f" Audit: {'enabled' if mcp_config.audit_enabled else 'disabled'}")
    click.echo("")

    async def _run():
        handle = await start_mcp_server(ctx_obj)
        if handle.task:
            with contextlib.suppress(asyncio.CancelledError):
                await handle.task

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        click.echo("\nMCP server stopped.")
