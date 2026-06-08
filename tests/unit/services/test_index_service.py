"""Index Service 单元测试。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app():
    from reqradar.index_svc.knowledge.writer import L3Writer
    from services.index.app import app

    app.state.checkpoints = {}
    app.state.knowledge_payloads = {}
    app.state.writer = L3Writer()
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


class TestIndexHealth:
    @pytest.mark.anyio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestIndexAPIKey:
    @pytest.mark.anyio
    async def test_no_key_returns_401(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/internal/v2/memory/query",
                params={"project_id": "p1", "query": "test"},
            )
            assert resp.status_code == 401


class TestMemoryQuery:
    @pytest.mark.anyio
    async def test_memory_query_returns_items(self, client):
        resp = await client.get(
            "/internal/v2/memory/query",
            params={
                "project_id": "test-project",
                "query": "authentication",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_memory_query_with_types(self, client):
        resp = await client.get(
            "/internal/v2/memory/query",
            params={
                "project_id": "test-project",
                "query": "test",
                "knowledge_types": "glossary,constraint",
                "top_k": 5,
            },
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_memory_query_missing_project_id(self, client):
        resp = await client.get("/internal/v2/memory/query", params={"query": "test"})
        assert resp.status_code == 422


class TestKnowledgeEndpoints:
    @pytest.mark.anyio
    async def test_knowledge_query(self, client):
        resp = await client.get(
            "/internal/v2/knowledge/query",
            params={"project_id": "test-project"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_knowledge_query_with_types(self, client):
        resp = await client.get(
            "/internal/v2/knowledge/query",
            params={
                "project_id": "test-project",
                "knowledge_types": "glossary,constraint",
                "limit": 5,
            },
        )
        assert resp.status_code == 200
