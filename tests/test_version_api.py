import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_reqradar_versions.db"
TEST_SECRET_KEY = "test-secret-key-versions"


@pytest_asyncio.fixture
async def setup_db():
    import reqradar.web.api.auth as auth_module
    import reqradar.web.dependencies as dep_module
    import reqradar.infrastructure.config as config_module

    original_secret = auth_module.SECRET_KEY
    original_expire = auth_module.ACCESS_TOKEN_EXPIRE_MINUTES
    original_factory = dep_module.async_session_factory
    original_config = config_module.load_config

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)

    dep_module.async_session_factory = session_factory
    auth_module.SECRET_KEY = TEST_SECRET_KEY
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = 1440

    def _test_config():
        c = original_config()
        c.web.auto_create_tables = True
        c.web.debug = True
        c.web.database_url = TEST_DATABASE_URL
        return c

    config_module.load_config = _test_config

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    dep_module.async_session_factory = original_factory
    auth_module.SECRET_KEY = original_secret
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire
    config_module.load_config = original_config

    db_path = "./test_reqradar_versions.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest_asyncio.fixture
async def auth_client(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={"email": "versions@example.com", "password": "secret123", "display_name": "Versions User"},
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "versions@example.com", "password": "secret123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        proj_resp = await client.post(
            "/api/projects/from-local",
            json={"name": "Versions-Project", "description": "test", "local_path": "/tmp"},
            headers=headers,
        )
        project_id = proj_resp.json()["id"]

        yield client, headers, project_id


@pytest.mark.asyncio
async def test_list_versions_empty(auth_client):
    client, headers, project_id = auth_client
    response = await client.get(
        "/api/analyses/1/reports/versions",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "versions" in data


@pytest.mark.asyncio
async def test_get_version_not_found(auth_client):
    client, headers, project_id = auth_client
    response = await client.get(
        "/api/analyses/999/reports/versions/1",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rollback_version_not_found(auth_client):
    client, headers, project_id = auth_client
    response = await client.post(
        "/api/analyses/999/reports/rollback",
        json={"version_number": 1},
        headers=headers,
    )
    assert response.status_code == 404
