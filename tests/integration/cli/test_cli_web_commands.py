from click.testing import CliRunner

from reqradar.cli.main import cli
from reqradar.web.models import User


def test_serve_invokes_uvicorn_with_configured_host_and_port(monkeypatch, test_config):
    import reqradar.cli.main as main_module
    import reqradar.web.cli as web_cli_module

    calls = []
    monkeypatch.setattr(main_module, "load_config", lambda path=None: test_config)
    monkeypatch.setattr(web_cli_module.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = CliRunner().invoke(cli, ["serve", "--host", "127.0.0.1", "--port", "8765"])

    assert result.exit_code == 0
    assert calls[0][1]["host"] == "127.0.0.1"
    assert calls[0][1]["port"] == 8765
    assert "Web UI" in result.output


def test_createsuperuser_creates_admin(monkeypatch, test_config, db_engine, session_factory):
    import asyncio

    import reqradar.cli.main as main_module

    monkeypatch.setattr(main_module, "load_config", lambda path=None: test_config)
    monkeypatch.setattr("reqradar.web.database.create_engine", lambda database_url: db_engine)
    monkeypatch.setattr("reqradar.web.database.create_session_factory", lambda engine: session_factory)

    result = CliRunner().invoke(
        cli,
        [
            "createsuperuser",
            "--email",
            "root@example.com",
            "--password",
            "Password123",
            "--display-name",
            "Root User",
        ],
    )

    async def fetch_user():
        async with session_factory() as session:
            return await session.get(User, 1)

    user = asyncio.run(fetch_user())

    assert result.exit_code == 0
    assert user.email == "root@example.com"
    assert user.role == "admin"


def test_createsuperuser_rejects_duplicate_email(monkeypatch, test_config, db_engine, session_factory):
    import reqradar.cli.main as main_module

    monkeypatch.setattr(main_module, "load_config", lambda path=None: test_config)
    monkeypatch.setattr("reqradar.web.database.create_engine", lambda database_url: db_engine)
    monkeypatch.setattr("reqradar.web.database.create_session_factory", lambda engine: session_factory)
    runner = CliRunner()
    args = [
        "createsuperuser",
        "--email",
        "root@example.com",
        "--password",
        "Password123",
        "--display-name",
        "Root User",
    ]

    first = runner.invoke(cli, args)
    second = runner.invoke(cli, args)

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "already exists" in second.output
