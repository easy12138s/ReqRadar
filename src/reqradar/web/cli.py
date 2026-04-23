import asyncio

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


@cli.command()
@click.option("--email", prompt=True, help="Admin email address")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Admin password")
@click.option("--display-name", prompt=True, help="Admin display name")
@click.pass_context
def createsuperuser(ctx, email, password, display_name):
    """Create a superuser (admin) account"""
    import bcrypt
    from sqlalchemy import select

    from reqradar.web.database import Base, create_engine, create_session_factory
    from reqradar.web.models import User

    config = ctx.obj["config"]
    web_config = config.web

    engine = create_engine(web_config.database_url)

    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()
            if existing is not None:
                click.echo(f"Error: User with email '{email}' already exists.")
                await engine.dispose()
                raise SystemExit(1)

            password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user = User(
                email=email,
                password_hash=password_hash,
                display_name=display_name,
                role="admin",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            click.echo(f"Superuser '{display_name}' ({email}) created successfully with id={user.id}.")

        await engine.dispose()

    asyncio.run(_create())