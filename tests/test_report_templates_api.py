import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory
from reqradar.web.dependencies import async_session_factory as dep_session_factory

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_reqradar_templates.db"
TEST_SECRET_KEY = "test-secret-key-templates"


@pytest_asyncio.fixture
async def setup_db():
    import reqradar.web.api.auth as auth_module
    import reqradar.web.dependencies as dep_module

    original_secret = auth_module.SECRET_KEY
    original_expire = auth_module.ACCESS_TOKEN_EXPIRE_MINUTES
    original_factory = dep_module.async_session_factory

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)

    dep_module.async_session_factory = session_factory
    auth_module.SECRET_KEY = TEST_SECRET_KEY
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = 1440

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    dep_module.async_session_factory = original_factory
    auth_module.SECRET_KEY = original_secret
    auth_module.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire

    db_path = "./test_reqradar_templates.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest_asyncio.fixture
async def auth_client(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={"email": "tpl@example.com", "password": "secret123", "display_name": "Template User"},
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "tpl@example.com", "password": "secret123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        yield client, headers


@pytest.mark.asyncio
async def test_list_templates(auth_client):
    client, headers = auth_client
    response = await client.get("/api/templates", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_template(auth_client):
    client, headers = auth_client
    response = await client.post(
        "/api/templates",
        json={
            "name": "Custom Template",
            "description": "A custom report template",
            "definition": "template_definition:\n  name: Custom\n  sections: []",
            "render_template": "# {{ title }}",
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Custom Template"
    assert data["is_default"] is False
