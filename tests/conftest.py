import os
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("REQRADAR_TESTING", "1")

from reqradar.infrastructure.config import Config, HomeConfig, WebConfig
from reqradar.infrastructure.paths import get_paths
from reqradar.web.api.auth import hash_password
from reqradar.web.app import create_app
from reqradar.web.database import Base
from reqradar.web.models import User
from reqradar.web.services.report_storage import ReportStorage


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    return Config(
        home=HomeConfig(path=str(tmp_path / "home")),
        web=WebConfig(
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
            secret_key="change-me-in-production",
            debug=True,
            auto_create_tables=False,
            data_root=str(tmp_path / "data"),
            reports_path=str(tmp_path / "reports"),
            max_upload_size=1,
        ),
    )


@pytest.fixture
async def db_engine(test_config: Config):
    engine = create_async_engine(test_config.web.database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    user = User(
        email="user@example.com",
        password_hash=hash_password("Password123"),
        display_name="Regular User",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        email="admin@example.com",
        password_hash=hash_password("Password123"),
        display_name="Admin User",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(app, regular_user: User) -> dict[str, str]:
    from reqradar.web.api.auth import create_access_token

    return {"Authorization": f"Bearer {create_access_token(regular_user.id)}"}


@pytest.fixture
def admin_headers(app, admin_user: User) -> dict[str, str]:
    from reqradar.web.api.auth import create_access_token

    return {"Authorization": f"Bearer {create_access_token(admin_user.id)}"}


@pytest.fixture
async def app(test_config: Config, session_factory, monkeypatch):
    import reqradar.infrastructure.config as config_module

    monkeypatch.setattr(config_module, "load_config", lambda path=None: test_config)
    app = create_app()
    paths = get_paths(test_config)
    app.state.config = test_config
    app.state.paths = paths
    app.state.session_factory = session_factory
    app.state.secret_key = test_config.web.secret_key
    app.state.report_storage = ReportStorage(paths["reports"])
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (repo / "README.md").write_text("# Sample\n", encoding="utf-8")
    return repo
