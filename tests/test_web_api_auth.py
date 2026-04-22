import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from reqradar.web.app import create_app
from reqradar.web.database import Base, create_engine, create_session_factory
from reqradar.web.dependencies import async_session_factory as dep_session_factory


TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_reqradar_auth.db"
TEST_SECRET_KEY = "test-secret-key-for-auth-tests"


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

    db_path = "./test_reqradar_auth.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_register_success(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "secret123", "display_name": "Test User"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["display_name"] == "Test User"
        assert data["role"] == "user"
        assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"email": "dup@example.com", "password": "secret123", "display_name": "User One"}
        response = await client.post("/api/auth/register", json=payload)
        assert response.status_code == 201

        response = await client.post("/api/auth/register", json=payload)
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={"email": "login@example.com", "password": "secret123", "display_name": "Login User"},
        )

        response = await client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "secret123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={"email": "wrongpw@example.com", "password": "secret123", "display_name": "Wrong PW User"},
        )

        response = await client.post(
            "/api/auth/login",
            json={"email": "wrongpw@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={"email": "me@example.com", "password": "secret123", "display_name": "Me User"},
        )

        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "me@example.com", "password": "secret123"},
        )
        token = login_resp.json()["access_token"]

        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_me_unauthenticated(setup_db):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me")
        assert response.status_code == 401