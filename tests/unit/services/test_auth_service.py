"""Auth Service 单元测试。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def app():
    from reqradar.kernel.database import Base, create_engine, create_session_factory
    from services.auth.app import app

    engine = create_engine("sqlite+aiosqlite://")
    session_factory = create_session_factory(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.db_session_factory = session_factory
    app.state.db_engine = engine
    yield app
    await engine.dispose()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Internal-API-Key": "dev-internal-key"},
    ) as c:
        yield c


@pytest.fixture
async def admin_token(client):
    resp = await client.post(
        "/internal/v2/auth/issue",
        json={
            "user_id": "admin-001",
            "username": "admin",
            "is_superuser": True,
        },
    )
    return resp.json()["token"]


class TestAuthHealth:
    @pytest.mark.anyio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200


class TestAuthIssue:
    @pytest.mark.anyio
    async def test_issue_token(self, client):
        resp = await client.post(
            "/internal/v2/auth/issue",
            json={
                "user_id": "u1",
                "username": "testuser",
                "is_superuser": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["token_type"] == "bearer"


class TestAuthVerify:
    @pytest.mark.anyio
    async def test_verify_valid_token(self, client, admin_token):
        resp = await client.post("/internal/v2/auth/verify", json={"token": admin_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert "jti" in data

    @pytest.mark.anyio
    async def test_verify_invalid_token(self, client):
        resp = await client.post("/internal/v2/auth/verify", json={"token": "invalid.jwt.token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["reason"] in (
            "TOKEN_EXPIRED",
            "TOKEN_INVALID",
            "TOKEN_MALFORMED",
            "TOKEN_UNKNOWN",
        )


class TestCheckPermission:
    @pytest.mark.anyio
    async def test_check_permission_allowed(self, client):
        resp = await client.post(
            "/internal/v2/auth/check-permission",
            json={
                "user_id": "admin-001",
                "resource": "/api/v2/sessions",
                "action": "read",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "allowed" in data

    @pytest.mark.anyio
    async def test_check_permission_unknown_user(self, client):
        resp = await client.post(
            "/internal/v2/auth/check-permission",
            json={
                "user_id": "nonexistent",
                "resource": "/api/v2/sessions",
                "action": "write",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is False


class TestGetUser:
    @pytest.mark.anyio
    async def test_get_user_not_found(self, client):
        resp = await client.get("/internal/v2/users/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "USER_NOT_FOUND"
