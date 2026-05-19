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

from tests.factories import unique_email


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


@pytest.fixture(scope="session")
async def session_scoped_db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
async def session_scoped_session_factory(session_scoped_db_engine):
    return async_sessionmaker(session_scoped_db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def test_user(client: AsyncClient) -> tuple:
    """Register + login a user, yield (client, headers, token, user_data)."""
    user_data = {
        "email": unique_email("testuser"),
        "password": "TestPass123",
        "display_name": "Test User",
    }
    resp = await client.post("/api/auth/register", json=user_data)
    assert resp.status_code == 201
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    yield (client, headers, token, user_data)


@pytest.fixture
async def test_project(test_user, tmp_path: Path) -> tuple:
    """Create a project, yield (client, headers, token, user_data, project_id)."""
    client, headers, token, user_data = test_user
    repo = tmp_path / "project_repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('hello')", encoding="utf-8")
    resp = await client.post(
        "/api/projects/from-local",
        headers=headers,
        json={
            "name": "test-project",
            "description": "Test",
            "local_path": str(repo),
        },
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]
    yield (client, headers, token, user_data, project_id)
