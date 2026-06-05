"""Integration Service 单元测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """带正确 Internal API Key 的测试客户端。"""
    from services.integration.app import app

    with TestClient(app, headers={"X-Internal-API-Key": "dev-internal-key"}) as c:
        yield c


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestHealth
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestHealth:
    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["service"] == "integration"
        assert body["status"] == "ok"

    def test_health_no_key_required(self):
        """健康检查无需 Internal API Key。"""
        from services.integration.app import app

        with TestClient(app) as c:
            resp = c.get("/health")
            assert resp.status_code == 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestInternalAPIKey
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestInternalAPIKey:
    def test_no_key_returns_401(self):
        from services.integration.app import app

        with TestClient(app) as c:
            resp = c.get("/internal/v2/mcp/keys")
            assert resp.status_code == 401

    def test_wrong_key_returns_401(self):
        from services.integration.app import app

        with TestClient(app, headers={"X-Internal-API-Key": "wrong"}) as c:
            resp = c.get("/internal/v2/mcp/keys")
            assert resp.status_code == 401

    def test_valid_key_passes(self, client: TestClient):
        resp = client.get("/internal/v2/mcp/keys")
        assert resp.status_code == 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestAccessKeys
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAccessKeys:
    def test_create_key(self, client: TestClient):
        resp = client.post("/internal/v2/mcp/keys", json={"name": "test-key"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["raw_key"].startswith("rr_mcp_")
        assert data["name"] == "test-key"

    def test_create_key_with_scopes(self, client: TestClient):
        resp = client.post(
            "/internal/v2/mcp/keys",
            json={"name": "scoped-key", "scopes": ["read", "write"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["scopes"] == ["read", "write"]

    def test_list_keys(self, client: TestClient):
        client.post("/internal/v2/mcp/keys", json={"name": "k1"})
        resp = client.get("/internal/v2/mcp/keys")
        assert resp.status_code == 200
        assert len(resp.json()["keys"]) >= 1

    def test_revoke_key(self, client: TestClient):
        create_resp = client.post("/internal/v2/mcp/keys", json={"name": "k2"})
        key_id = create_resp.json()["key_id"]
        resp = client.post(f"/internal/v2/mcp/keys/{key_id}/revoke")
        assert resp.status_code == 200
        assert resp.json()["revoked"] is True

    def test_revoke_nonexistent_key(self, client: TestClient):
        resp = client.post("/internal/v2/mcp/keys/nonexistent/revoke")
        assert resp.status_code == 404

    def test_list_keys_after_revoke_shows_status(self, client: TestClient):
        create_resp = client.post("/internal/v2/mcp/keys", json={"name": "k3"})
        key_id = create_resp.json()["key_id"]
        client.post(f"/internal/v2/mcp/keys/{key_id}/revoke")
        resp = client.get("/internal/v2/mcp/keys")
        keys = resp.json()["keys"]
        revoked_keys = [k for k in keys if k["key_id"] == key_id]
        assert len(revoked_keys) == 1
        assert revoked_keys[0]["status"] == "revoked"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestAuditLog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAuditLog:
    def test_get_audit_log(self, client: TestClient):
        resp = client.get("/internal/v2/mcp/audit")
        assert resp.status_code == 200
        assert "entries" in resp.json()

    def test_audit_cleanup(self, client: TestClient):
        resp = client.post("/internal/v2/mcp/audit/cleanup")
        assert resp.status_code == 200
        assert "removed" in resp.json()

    def test_audit_log_empty_after_cleanup(self, client: TestClient):
        client.post("/internal/v2/mcp/audit/cleanup")
        resp = client.get("/internal/v2/mcp/audit")
        assert resp.json()["entries"] == []

    def test_audit_log_with_limit(self, client: TestClient):
        resp = client.get("/internal/v2/mcp/audit?limit=10")
        assert resp.status_code == 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestKeyManager
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestKeyManager:
    def test_generate_key_format(self):
        from services.integration.mcp_keys import KeyManager

        km = KeyManager()
        raw_key, ak = km.generate_key("test")
        assert raw_key.startswith("rr_mcp_")
        assert len(raw_key) > 10

    def test_verify_valid_key(self):
        from services.integration.mcp_keys import KeyManager

        km = KeyManager()
        raw_key, _ = km.generate_key("test")
        result = km.verify_key(raw_key)
        assert result is not None

    def test_verify_revoked_key(self):
        from services.integration.mcp_keys import KeyManager

        km = KeyManager()
        raw_key, ak = km.generate_key("test")
        km.revoke_key(ak.key_id)
        assert km.verify_key(raw_key) is None

    def test_verify_invalid_key(self):
        from services.integration.mcp_keys import KeyManager

        km = KeyManager()
        assert km.verify_key("invalid_key") is None

    def test_generate_multiple_keys_unique(self):
        from services.integration.mcp_keys import KeyManager

        km = KeyManager()
        raw1, ak1 = km.generate_key("k1")
        raw2, ak2 = km.generate_key("k2")
        assert raw1 != raw2
        assert ak1.key_id != ak2.key_id

    def test_revoke_nonexistent_returns_false(self):
        from services.integration.mcp_keys import KeyManager

        km = KeyManager()
        assert km.revoke_key("nonexistent") is False

    def test_list_keys_empty(self):
        from services.integration.mcp_keys import KeyManager

        km = KeyManager()
        assert km.list_keys() == []

    def test_list_keys_returns_all(self):
        from services.integration.mcp_keys import KeyManager

        km = KeyManager()
        km.generate_key("k1")
        km.generate_key("k2")
        assert len(km.list_keys()) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestAuditSanitization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAuditSanitization:
    def test_sanitize_sensitive_fields(self):
        from services.integration.mcp_audit import sanitize_arguments

        args = {"token": "secret123", "query": "test", "password": "abc"}
        result = sanitize_arguments(args)
        assert result["token"] == "***REDACTED***"
        assert result["password"] == "***REDACTED***"
        assert result["query"] == "test"

    def test_sanitize_nested(self):
        from services.integration.mcp_audit import sanitize_arguments

        args = {"data": {"api_key": "secret", "name": "test"}}
        result = sanitize_arguments(args)
        assert result["data"]["api_key"] == "***REDACTED***"
        assert result["data"]["name"] == "test"

    def test_sanitize_preserves_normal_fields(self):
        from services.integration.mcp_audit import sanitize_arguments

        args = {"query": "hello", "limit": 10, "enabled": True}
        result = sanitize_arguments(args)
        assert result == args

    def test_sanitize_list_of_dicts(self):
        from services.integration.mcp_audit import sanitize_arguments

        args = {"items": [{"secret": "val1", "id": 1}, {"id": 2}]}
        result = sanitize_arguments(args)
        assert result["items"][0]["secret"] == "***REDACTED***"
        assert result["items"][0]["id"] == 1

    def test_audit_record(self):
        from services.integration.mcp_audit import AuditLog

        log = AuditLog()
        entry = log.record(
            tool_name="test_tool",
            arguments={"token": "secret", "query": "test"},
            result_summary="ok",
            duration_ms=100,
        )
        assert entry.sanitized_arguments["token"] == "***REDACTED***"
        assert entry.sanitized_arguments["query"] == "test"

    def test_audit_query(self):
        from services.integration.mcp_audit import AuditLog

        log = AuditLog()
        log.record(tool_name="tool_a", arguments={}, result_summary="ok", duration_ms=10)
        log.record(tool_name="tool_b", arguments={}, result_summary="ok", duration_ms=20)
        assert len(log.query(tool_name="tool_a")) == 1
        assert len(log.query(tool_name="tool_b")) == 1

    def test_audit_query_by_key_id(self):
        from services.integration.mcp_audit import AuditLog

        log = AuditLog()
        log.record(tool_name="t", arguments={}, result_summary="ok", duration_ms=5, key_id="k1")
        log.record(tool_name="t", arguments={}, result_summary="ok", duration_ms=5, key_id="k2")
        assert len(log.query(key_id="k1")) == 1
        assert len(log.query(key_id="k2")) == 1

    def test_audit_cleanup_returns_count(self):
        from services.integration.mcp_audit import AuditLog

        log = AuditLog()
        log.record(tool_name="t1", arguments={}, result_summary="ok", duration_ms=10)
        log.record(tool_name="t2", arguments={}, result_summary="ok", duration_ms=20)
        removed = log.cleanup()
        assert removed == 2
        assert log.query() == []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TestMCPConfig
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMCPConfig:
    def test_get_config(self, client: TestClient):
        resp = client.get("/internal/v2/mcp/config")
        assert resp.status_code == 200
        body = resp.json()
        assert "mcp_running" in body
        assert body["mcp_running"] is True

    def test_config_contains_port(self, client: TestClient):
        resp = client.get("/internal/v2/mcp/config")
        body = resp.json()
        assert "mcp_port" in body
        assert isinstance(body["mcp_port"], int)
