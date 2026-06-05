"""API Service BFF 综合测试 — 30+ 测试覆盖全部路由与认证依赖。"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

VALID_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
VALID_USER = {
    "user_id": "u-001",
    "username": "tester",
    "email": "tester@example.com",
    "role": "user",
    "is_active": True,
}
AUTH_HEADER = {"Authorization": f"Bearer {VALID_TOKEN}"}


@pytest.fixture()
def mock_client():
    """构造一个全部方法都 stub 化的 AsyncMock ServiceClient。"""
    client = AsyncMock()

    client.verify_token.return_value = {"valid": True, "user": VALID_USER}

    client.create_session.return_value = {
        "session_id": "s-001",
        "project_id": "p-001",
        "status": "READY",
        "created_at": "2026-06-01T10:00:00Z",
        "config": {},
        "state": {"context_usage": 0, "current_step": 0, "current_phase": "INIT"},
    }

    client.get_session.return_value = {
        "session_id": "s-001",
        "project_id": "p-001",
        "status": "RUNNING",
        "created_at": "2026-06-01T10:00:00Z",
        "started_at": "2026-06-01T10:00:05Z",
        "finished_at": None,
        "config": {},
        "state": {"context_usage": 45000, "current_step": 12, "current_phase": "ANALYSIS"},
    }

    client.start_session.return_value = {
        "session_id": "s-001",
        "status": "RUNNING",
        "started_at": "2026-06-01T10:00:05Z",
        "resumed_from_version": None,
        "state": {"context_usage": 0, "current_step": 0, "current_phase": "INIT"},
    }

    client.cancel_session.return_value = {
        "session_id": "s-001",
        "status": "CANCELLING",
        "message": "Cancellation requested",
    }

    client.create_checkpoint.return_value = {
        "checkpoint_id": "cp-001",
        "version": 4,
        "session_id": "s-001",
        "type": "MANUAL",
        "created_at": "2026-06-01T10:05:00Z",
    }

    client.get_events.return_value = {
        "session_id": "s-001",
        "events": [
            {
                "event_id": "ev-001",
                "sequence": 1,
                "event_type": "SESSION_STARTED",
                "event_level": "session",
                "timestamp": "2026-06-01T10:00:05Z",
                "producer": "cognitive-rt",
                "payload": {},
            }
        ],
        "total": 1,
        "has_more": False,
    }

    client.get_evidence.return_value = {
        "total": 1,
        "items": [
            {
                "id": "ev-abc",
                "session_id": "s-001",
                "type": "code_evidence",
                "status": "verified",
                "confidence": {"score": 0.85, "level": "high"},
                "content": "支付模块无分布式锁保护",
            }
        ],
    }

    client.get_evidence_detail.return_value = {
        "evidence": {
            "id": "ev-abc",
            "session_id": "s-001",
            "type": "code_evidence",
            "status": "verified",
        },
        "relations": [],
    }

    client.verify_evidence.return_value = {
        "evidence": {"id": "ev-abc", "status": "verified"},
        "previous_status": "discovered",
        "confidence_delta": 0.1,
    }

    client.get_dimensions.return_value = {
        "session_id": "s-001",
        "dimensions": {
            "completeness": {"status": "sufficient", "evidence_count": 5, "risk_level": "low"},
            "consistency": {"status": "in_progress", "evidence_count": 2, "risk_level": "medium"},
        },
        "completed_count": 1,
        "pending_count": 6,
    }

    client.get_checkpoints.return_value = {
        "session_id": "s-001",
        "total": 3,
        "items": [
            {
                "checkpoint_id": "cp-001",
                "version": 3,
                "type": "STEP_COMPLETE",
                "created_at": "2026-06-01T10:03:00Z",
                "state_summary": {},
            }
        ],
        "has_more": False,
    }

    client.get_checkpoint_version.return_value = {
        "checkpoint_id": "cp-001",
        "version": 3,
        "type": "STEP_COMPLETE",
        "created_at": "2026-06-01T10:03:00Z",
        "state_summary": {},
        "diff": {"added": [], "removed": [], "modified": []},
        "metadata": {"duration_ms": 1200},
    }

    client.restore_checkpoint.return_value = {
        "session_id": "s-001",
        "status": "RUNNING",
        "restored_from_version": 3,
        "state": {"context_usage": 45000, "current_step": 13, "current_phase": "ANALYSIS"},
    }

    client.get_trace.return_value = {
        "session_id": "s-001",
        "session_events": [],
        "steps": [],
    }

    client.get_knowledge.return_value = {
        "project_id": "p-001",
        "summaries": {
            "glossary": {"total": 5, "active": 4, "avg_confidence": 0.75},
        },
        "top_items": {},
    }

    client.search_knowledge.return_value = {
        "items": [
            {
                "id": "k-001",
                "knowledge_type": "glossary",
                "data": {"canonical_name": "points_engine"},
                "score": 0.92,
            }
        ],
        "total": 1,
    }

    client.get_knowledge_detail.return_value = {
        "id": "k-001",
        "knowledge_type": "glossary",
        "data": {"canonical_name": "points_engine", "definition": "积分计算引擎"},
        "freshness": "active",
        "confidence_score": 0.8,
    }

    client.update_knowledge.return_value = {
        "id": "k-001",
        "knowledge_type": "glossary",
        "data": {"canonical_name": "points_engine", "definition": "积分计算引擎 v2"},
    }

    client.deprecate_knowledge.return_value = {
        "id": "k-001",
        "knowledge_type": "constraint",
        "freshness": "deprecated",
    }

    client.get_graph_neighbors.return_value = {
        "center": {"type": "constraint", "id": "c-001"},
        "neighbors": [
            {"type": "risk", "id": "r-001", "relation_type": "VIOLATES", "confidence": 0.8}
        ],
        "total": 1,
    }

    client.get_graph_path.return_value = {
        "from": {"type": "risk", "id": "r-001"},
        "to": {"type": "incident", "id": "i-001"},
        "paths": [{"length": 2, "edges": []}],
        "found": True,
    }

    client.get_graph_subgraph.return_value = {
        "nodes": [{"type": "risk", "id": "r-001", "label": "并发扣减积分"}],
        "edges": [],
        "total_nodes": 1,
        "total_edges": 0,
    }

    client.generate_report.return_value = {
        "task_id": "t-001",
        "status": "queued",
        "estimated_duration_ms": 5000,
    }

    client.get_report_status.return_value = {
        "task_id": "t-001",
        "status": "completed",
        "output_uri": "minio://reports/s-001/report.md",
        "format": "markdown",
        "size_bytes": 12345,
        "completed_at": "2026-06-01T10:05:00Z",
    }

    client.create_mcp_key.return_value = {
        "key_id": "k1",
        "raw_key": "rr_mcp_abc123",
        "name": "test",
        "scopes": ["read"],
    }

    client.list_mcp_keys.return_value = {"keys": []}

    client.revoke_mcp_key.return_value = {"key_id": "k1", "revoked": True}

    client.get_mcp_audit.return_value = {"entries": [], "total": 0}

    client.get_mcp_config.return_value = {"mcp_running": True, "mcp_port": 9000}

    return client


@pytest.fixture()
def client(mock_client):
    """通过 dependency_overrides 注入 mock，同时替换模块级 service_client。"""
    import services.api.app as app_module
    from services.api.app import app, get_current_user

    app.dependency_overrides[get_current_user] = lambda: VALID_USER
    app_module.service_client = mock_client

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app_module.service_client = app_module.ServiceClient()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestHealth
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestHealth:
    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "api"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestAuthMiddleware
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAuthMiddleware:
    def test_missing_token_returns_401(self, mock_client):
        import services.api.app as app_module
        from services.api.app import app, get_current_user

        app.dependency_overrides.clear()
        app_module.service_client = mock_client

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v2/sessions/s-001")
            assert resp.status_code == 401

        app.dependency_overrides[get_current_user] = lambda: VALID_USER

    def test_invalid_token_returns_401(self, mock_client):
        import services.api.app as app_module
        from services.api.app import app, get_current_user

        mock_client.verify_token.return_value = {"valid": False, "error": "expired"}
        app.dependency_overrides.clear()
        app_module.service_client = mock_client

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get(
                "/api/v2/sessions/s-001",
                headers={"Authorization": "Bearer bad-token"},
            )
            assert resp.status_code == 401

        app.dependency_overrides[get_current_user] = lambda: VALID_USER
        mock_client.verify_token.return_value = {"valid": True, "user": VALID_USER}

    def test_valid_token_passes(self, client: TestClient):
        resp = client.get("/api/v2/sessions/s-001", headers=AUTH_HEADER)
        assert resp.status_code == 200

    def test_token_content_not_leaked(self, mock_client):
        import services.api.app as app_module
        from services.api.app import app, get_current_user

        mock_client.verify_token.return_value = {"valid": False, "error": "expired"}
        app.dependency_overrides.clear()
        app_module.service_client = mock_client

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get(
                "/api/v2/sessions/s-001",
                headers={"Authorization": "Bearer secret-token-value"},
            )
            assert "secret-token-value" not in resp.text

        app.dependency_overrides[get_current_user] = lambda: VALID_USER
        mock_client.verify_token.return_value = {"valid": True, "user": VALID_USER}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestSessionRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSessionRoutes:
    def test_create_session(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/sessions",
            json={"project_id": "p-001"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["session_id"] == "s-001"
        assert body["status"] == "READY"
        mock_client.create_session.assert_called_once()

    def test_get_session(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get("/api/v2/sessions/s-001", headers=AUTH_HEADER)
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "s-001"
        assert body["status"] == "RUNNING"
        mock_client.get_session.assert_called_once()
        args = mock_client.get_session.call_args[0]
        assert args[0] == "s-001"

    def test_start_session(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/sessions/s-001/start",
            json={},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "RUNNING"
        mock_client.start_session.assert_called_once()
        args = mock_client.start_session.call_args[0]
        assert args[0] == "s-001"
        assert args[1] is None

    def test_cancel_session(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/sessions/s-001/cancel",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "CANCELLING"
        mock_client.cancel_session.assert_called_once()

    def test_create_checkpoint(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/sessions/s-001/checkpoint",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["checkpoint_id"] == "cp-001"
        assert body["version"] == 4
        mock_client.create_checkpoint.assert_called_once()

    def test_get_events(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/sessions/s-001/events?limit=50",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "s-001"
        assert len(body["events"]) == 1
        mock_client.get_events.assert_called_once()
        args = mock_client.get_events.call_args[0]
        assert args[0] == "s-001"
        assert args[1]["limit"] == 50

    def test_websocket_stub(self, client: TestClient):
        with client.websocket_connect("/api/v2/sessions/s-001/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "info"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestEvidenceRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestEvidenceRoutes:
    def test_get_evidence(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/sessions/s-001/evidence",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == "ev-abc"
        mock_client.get_evidence.assert_called_once()

    def test_get_evidence_detail(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/sessions/s-001/evidence/ev-abc",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["evidence"]["id"] == "ev-abc"
        assert body["relations"] == []
        mock_client.get_evidence_detail.assert_called_once()
        args = mock_client.get_evidence_detail.call_args[0]
        assert args[0] == "s-001"
        assert args[1] == "ev-abc"

    def test_verify_evidence(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/sessions/s-001/evidence/ev-abc/verify",
            json={"verified_by": "auto"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["previous_status"] == "discovered"
        assert body["confidence_delta"] == 0.1
        mock_client.verify_evidence.assert_called_once()
        args = mock_client.verify_evidence.call_args[0]
        assert args[0] == "s-001"
        assert args[1] == "ev-abc"
        assert args[2] == "auto"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestDimensionRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDimensionRoutes:
    def test_get_dimensions(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/sessions/s-001/dimensions",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "s-001"
        assert "completeness" in body["dimensions"]
        assert body["completed_count"] == 1
        mock_client.get_dimensions.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestCheckpointRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCheckpointRoutes:
    def test_get_checkpoints(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/sessions/s-001/checkpoints",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "s-001"
        assert body["total"] == 3
        mock_client.get_checkpoints.assert_called_once()

    def test_get_checkpoint_version(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/sessions/s-001/checkpoints/3",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == 3
        assert body["checkpoint_id"] == "cp-001"
        mock_client.get_checkpoint_version.assert_called_once()

    def test_restore_checkpoint(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/sessions/s-001/checkpoints/3/restore",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "RUNNING"
        assert body["restored_from_version"] == 3
        mock_client.restore_checkpoint.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestKnowledgeRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestKnowledgeRoutes:
    def test_get_knowledge(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/projects/p-001/knowledge",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == "p-001"
        assert "glossary" in body["summaries"]
        mock_client.get_knowledge.assert_called_once()

    def test_search_knowledge(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/projects/p-001/knowledge",
            json={"query": "支付模块并发风险"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["knowledge_type"] == "glossary"
        mock_client.search_knowledge.assert_called_once()

    def test_get_knowledge_detail(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/projects/p-001/knowledge/k-001?knowledge_type=glossary",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "k-001"
        assert body["knowledge_type"] == "glossary"
        mock_client.get_knowledge_detail.assert_called_once()

    def test_update_knowledge(self, mock_client: AsyncMock, client: TestClient):
        resp = client.put(
            "/api/v2/projects/p-001/knowledge/k-001",
            json={
                "knowledge_type": "glossary",
                "patch": {"definition": "积分计算引擎 v2"},
            },
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["definition"] == "积分计算引擎 v2"
        mock_client.update_knowledge.assert_called_once()

    def test_deprecate_knowledge(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/projects/p-001/knowledge/k-001/deprecate",
            json={"knowledge_type": "constraint", "reason": "该约束已不适用于新架构"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["freshness"] == "deprecated"
        mock_client.deprecate_knowledge.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestGraphRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGraphRoutes:
    def test_get_neighbors(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/projects/p-001/graph/neighbors?node_type=constraint&node_id=c-001",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["neighbors"][0]["type"] == "risk"
        mock_client.get_graph_neighbors.assert_called_once()

    def test_get_path(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/projects/p-001/graph/path?from_type=risk&from_id=r-001&to_type=incident&to_id=i-001",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["found"] is True
        assert len(body["paths"]) == 1
        mock_client.get_graph_path.assert_called_once()

    def test_get_subgraph(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/projects/p-001/graph/subgraph",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_nodes"] == 1
        mock_client.get_graph_subgraph.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestTraceRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTraceRoutes:
    def test_get_trace(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/sessions/s-001/trace",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "s-001"
        assert "steps" in body
        mock_client.get_trace.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestReportRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestReportRoutes:
    def test_generate_report(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/reports/generate",
            json={"session_id": "s-001"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["task_id"] == "t-001"
        assert body["status"] == "queued"
        mock_client.generate_report.assert_called_once()
        args = mock_client.generate_report.call_args[0]
        assert args[0] == "s-001"

    def test_report_status(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/reports/t-001/status",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "t-001"
        assert body["status"] == "completed"
        mock_client.get_report_status.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestInternalKeyInjection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestInternalKeyInjection:
    def test_verify_token_called_with_token(self, mock_client: AsyncMock):
        import services.api.app as app_module
        from services.api.app import app, get_current_user

        app.dependency_overrides.clear()
        mock_client.verify_token.return_value = {"valid": True, "user": VALID_USER}
        app_module.service_client = mock_client

        with TestClient(app, raise_server_exceptions=False) as c:
            c.get("/api/v2/sessions/s-001", headers=AUTH_HEADER)
            mock_client.verify_token.assert_called_once_with(VALID_TOKEN)

        app.dependency_overrides[get_current_user] = lambda: VALID_USER

    def test_jwt_forwarded_to_downstream(self, mock_client: AsyncMock, client: TestClient):
        client.get("/api/v2/sessions/s-001", headers=AUTH_HEADER)
        mock_client.get_session.assert_called_once()
        args = mock_client.get_session.call_args[0]
        assert len(args) >= 2
        assert args[1] == VALID_TOKEN


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestNoDatabaseAccess
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestNoDatabaseAccess:
    def test_no_sqlalchemy_import(self):
        api_dir = Path(__file__).resolve().parents[3] / "services" / "api"
        for py_file in api_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert (
                            "sqlalchemy" not in alias.name.lower()
                        ), f"{py_file.name} 导入了 sqlalchemy: {alias.name}"
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert (
                        "sqlalchemy" not in node.module.lower()
                    ), f"{py_file.name} 从 sqlalchemy 导入: {node.module}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestMCPProxyRoutes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMCPProxyRoutes:
    """BFF MCP 管理代理路由测试。"""

    def test_create_mcp_key(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/mcp/keys",
            json={"name": "test"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["key_id"] == "k1"
        assert body["raw_key"] == "rr_mcp_abc123"
        mock_client.create_mcp_key.assert_called_once()

    def test_list_mcp_keys(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/mcp/keys",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["keys"] == []
        mock_client.list_mcp_keys.assert_called_once()

    def test_revoke_mcp_key(self, mock_client: AsyncMock, client: TestClient):
        resp = client.post(
            "/api/v2/mcp/keys/k1/revoke",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["key_id"] == "k1"
        assert body["revoked"] is True
        mock_client.revoke_mcp_key.assert_called_once()

    def test_get_mcp_audit(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/mcp/audit",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["entries"] == []
        assert body["total"] == 0
        mock_client.get_mcp_audit.assert_called_once()

    def test_get_mcp_config(self, mock_client: AsyncMock, client: TestClient):
        resp = client.get(
            "/api/v2/mcp/config",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mcp_running"] is True
        assert body["mcp_port"] == 9000
        mock_client.get_mcp_config.assert_called_once()
