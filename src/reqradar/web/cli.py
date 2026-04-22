import click
import uvicorn

from reqradar.cli.main import cli


@cli.command()
@click.option("--host", default=None, help="Bind host (overrides config)")
@click.option("--port", default=None, type=int, help="Bind port (overrides config)")
@click.option("--reload/--no-reload", default=False, help="Enable auto-reload for development")
@click.pass_context
def serve(ctx, host, port, reload):
    """Start the ReqRadar web server"""
    config = ctx.obj["config"]
    web_config = config.web

    serve_host = host or web_config.host
    serve_port = port or web_config.port

    click.echo(f"Starting ReqRadar on {serve_host}:{serve_port}")

    uvicorn.run(
        "reqradar.web.app:create_app",
        host=serve_host,
        port=serve_port,
        factory=True,
        reload=reload,
    )