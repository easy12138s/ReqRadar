"""Cognitive-RT Server 单元测试。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    from reqradar.cognitive_rt.runtime.server import app

    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Internal-API-Key": "dev-internal-key"},
    ) as c:
        yield c


class TestHealth:
    @pytest.mark.anyio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAPIKey:
    @pytest.mark.anyio
    async def test_no_key_returns_401(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/internal/v2/sessions/nonexistent")
            assert resp.status_code == 401


class TestCreateSession:
    @pytest.mark.anyio
    async def test_create_session(self, client):
        resp = await client.post(
            "/internal/v2/sessions",
            json={
                "project_id": "test-project",
                "user_id": "test-user",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["status"] in ("CREATED", "READY")


class TestGetSession:
    @pytest.mark.anyio
    async def test_get_session_not_found(self, client):
        resp = await client.get("/internal/v2/sessions/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert data["detail"]["error"]["code"] == "SESSION_NOT_FOUND"


class TestStartSession:
    @pytest.mark.anyio
    async def test_start_session(self, client):
        create_resp = await client.post(
            "/internal/v2/sessions",
            json={
                "project_id": "test-project",
                "user_id": "test-user",
            },
        )
        session_id = create_resp.json()["session_id"]
        resp = await client.post(f"/internal/v2/sessions/{session_id}/start", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "RUNNING"


class TestCancelSession:
    @pytest.mark.anyio
    async def test_cancel_ready_session(self, client):
        create_resp = await client.post(
            "/internal/v2/sessions",
            json={
                "project_id": "test-project",
                "user_id": "test-user",
            },
        )
        session_id = create_resp.json()["session_id"]
        resp = await client.post(f"/internal/v2/sessions/{session_id}/cancel")
        assert resp.status_code == 202


class TestEvidence:
    @pytest.mark.anyio
    async def test_get_evidence_empty(self, client):
        create_resp = await client.post(
            "/internal/v2/sessions",
            json={
                "project_id": "test-project",
                "user_id": "test-user",
            },
        )
        session_id = create_resp.json()["session_id"]
        resp = await client.get(f"/internal/v2/sessions/{session_id}/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_get_evidence_not_found(self, client):
        resp = await client.get("/internal/v2/sessions/nonexistent/evidence")
        assert resp.status_code == 404


class TestDimensions:
    @pytest.mark.anyio
    async def test_get_dimensions(self, client):
        create_resp = await client.post(
            "/internal/v2/sessions",
            json={
                "project_id": "test-project",
                "user_id": "test-user",
            },
        )
        session_id = create_resp.json()["session_id"]
        resp = await client.get(f"/internal/v2/sessions/{session_id}/dimensions")
        assert resp.status_code == 200
        data = resp.json()
        assert "dimensions" in data

    @pytest.mark.anyio
    async def test_get_dimensions_not_found(self, client):
        resp = await client.get("/internal/v2/sessions/nonexistent/dimensions")
        assert resp.status_code == 404


class TestCheckpoints:
    @pytest.mark.anyio
    async def test_create_checkpoint(self, client):
        create_resp = await client.post(
            "/internal/v2/sessions",
            json={
                "project_id": "test-project",
                "user_id": "test-user",
            },
        )
        session_id = create_resp.json()["session_id"]
        await client.post(f"/internal/v2/sessions/{session_id}/start", json={})
        resp = await client.post(f"/internal/v2/sessions/{session_id}/checkpoint")
        assert resp.status_code == 200
        assert "checkpoint_id" in resp.json()


class TestEvents:
    @pytest.mark.anyio
    async def test_get_events(self, client):
        create_resp = await client.post(
            "/internal/v2/sessions",
            json={
                "project_id": "test-project",
                "user_id": "test-user",
            },
        )
        session_id = create_resp.json()["session_id"]
        resp = await client.get(f"/internal/v2/sessions/{session_id}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
