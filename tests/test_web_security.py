import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory


TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_reqradar_security.db"
TEST_SECRET_KEY = "test-secret-key-for-security-tests"


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

    db_path = "./test_reqradar_security.db"
    if os.path.exists(db_path):
        os.remove(db_path)


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "secret123", "display_name": email},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "secret123"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_upload_rejects_dangerous_extension(setup_db):
    import io

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(client, "upload_sec@example.com")

        resp = await client.post(
            "/api/projects/from-local",
            json={"name": "Upload-Sec-Project", "description": "test", "local_path": "/tmp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        dangerous_file = io.BytesIO(b"malicious content")
        resp = await client.post(
            "/api/analyses/upload",
            data={"project_id": str(project_id), "requirement_name": "test"},
            files={"file": ("evil.sh", dangerous_file, "application/x-sh")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_accepts_allowed_extension(setup_db):
    import io

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(client, "upload_ok@example.com")

        resp = await client.post(
            "/api/projects/from-local",
            json={"name": "Upload-OK-Project", "description": "test", "local_path": "/tmp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        safe_file = io.BytesIO(b"some requirement text")
        resp = await client.post(
            "/api/analyses/upload",
            data={"project_id": str(project_id), "requirement_name": "test"},
            files={"file": ("requirement.txt", safe_file, "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
