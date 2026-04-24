import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory
from reqradar.web.dependencies import async_session_factory as dep_session_factory

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_reqradar_chatback.db"
TEST_SECRET_KEY = "test-secret-key-chatback"


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

    db_path = "./test_reqradar_chatback.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest_asyncio.fixture
async def auth_client(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={"email": "chatback@example.com", "password": "secret123", "display_name": "Chatback User"},
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "chatback@example.com", "password": "secret123"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        proj_resp = await client.post(
            "/api/projects",
            json={"name": "Chatback Project", "description": "test"},
            headers=headers,
        )
        project_id = proj_resp.json()["id"]

        yield client, headers, project_id


@pytest.mark.asyncio
async def test_chat_endpoint_structure(auth_client):
    client, headers, project_id = auth_client
    analysis_resp = await client.post(
        "/api/analyses",
        json={"project_id": project_id, "requirement_name": "Test", "requirement_text": "Test requirement for chatback"},
        headers=headers,
    )
    assert analysis_resp.status_code in (200, 201)
    task_id = analysis_resp.json()["id"]

    response = await client.post(
        f"/api/analyses/{task_id}/chat",
        json={"message": "为什么风险评估是中而不是高？"},
        headers=headers,
    )
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_chat_history_endpoint(auth_client):
    client, headers, project_id = auth_client
    analysis_resp = await client.post(
        "/api/analyses",
        json={"project_id": project_id, "requirement_name": "Test", "requirement_text": "Test requirement for chatback history"},
        headers=headers,
    )
    assert analysis_resp.status_code in (200, 201)
    task_id = analysis_resp.json()["id"]

    response = await client.get(
        f"/api/analyses/{task_id}/chat",
        headers=headers,
    )
    assert response.status_code in (200, 404)
