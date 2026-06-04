"""P2 基础设施集成测试 — JWT 认证 / Internal API Key 中间件 / Redis 客户端。"""

from __future__ import annotations

import time
import types
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reqradar.infrastructure.auth import (
    create_jwt_token,
    create_mock_token,
    decode_jwt_token,
)
from reqradar.infrastructure.internal_auth import InternalAPIKeyMiddleware
from reqradar.infrastructure.redis_client import RedisClient

# ---------------------------------------------------------------------------
# TestJWTAuth — JWT 认证测试
# ---------------------------------------------------------------------------


class TestJWTAuth:
    def test_create_jwt_token(self):
        token = create_jwt_token("user-001", "alice", secret="s3cret", use_mock=True)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_jwt_token(self):
        secret = "test-secret"
        token = create_jwt_token("user-002", "bob", secret=secret, use_mock=True)
        payload = decode_jwt_token(token, secret=secret, use_mock=True)
        assert payload["sub"] == "user-002"
        assert payload["username"] == "bob"
        assert "iat" in payload
        assert "exp" in payload

    def test_decode_invalid_token(self):
        with pytest.raises(ValueError):
            decode_jwt_token("not-a-valid-token", secret="any", use_mock=True)

    def test_decode_expired_token(self):
        secret = "exp-secret"
        now = int(time.time())
        payload = {"sub": "u1", "username": "test", "iat": now, "exp": now - 10}
        token = create_mock_token(payload, secret)
        with pytest.raises(ValueError, match="过期"):
            decode_jwt_token(token, secret=secret, use_mock=True)

    def test_mock_token_fallback(self):
        fake_jwt = types.ModuleType("jwt")
        fake_jwt.encode = mock.Mock(side_effect=ImportError)
        fake_jwt.decode = mock.Mock(side_effect=ImportError)

        import reqradar.infrastructure.auth as auth_mod

        original_has = auth_mod._HAS_PYJWT
        original_jwt = auth_mod._jwt
        try:
            auth_mod._HAS_PYJWT = False
            auth_mod._jwt = None
            token = create_jwt_token("u-mock", "mockuser", secret="sec")
            assert token.startswith("mock.")
            payload = decode_jwt_token(token, secret="sec")
            assert payload["sub"] == "u-mock"
            assert payload["username"] == "mockuser"
        finally:
            auth_mod._HAS_PYJWT = original_has
            auth_mod._jwt = original_jwt


# ---------------------------------------------------------------------------
# TestInternalAPIKeyMiddleware — 内部 API Key 中间件测试
# ---------------------------------------------------------------------------


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(InternalAPIKeyMiddleware, api_key="test-key")

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/internal/v2/checkpoints")
    async def checkpoints():
        return {"data": []}

    @app.get("/api/v2/sessions")
    async def sessions():
        return {"sessions": []}

    return app


class TestInternalAPIKeyMiddleware:
    def test_public_path_no_auth(self):
        client = TestClient(_create_test_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_internal_path_with_valid_key(self):
        client = TestClient(_create_test_app())
        resp = client.get(
            "/internal/v2/checkpoints",
            headers={"X-Internal-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"data": []}

    def test_internal_path_without_key(self):
        client = TestClient(_create_test_app())
        resp = client.get("/internal/v2/checkpoints")
        assert resp.status_code == 403

    def test_internal_path_with_wrong_key(self):
        client = TestClient(_create_test_app())
        resp = client.get(
            "/internal/v2/checkpoints",
            headers={"X-Internal-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403

    def test_non_internal_path_no_auth(self):
        client = TestClient(_create_test_app())
        resp = client.get("/api/v2/sessions")
        assert resp.status_code == 200
        assert resp.json() == {"sessions": []}


# ---------------------------------------------------------------------------
# TestRedisClient — Redis 客户端（内存降级模式）测试
# ---------------------------------------------------------------------------


class TestRedisClient:
    @pytest.mark.asyncio
    async def test_connect_fallback(self):
        client = RedisClient(url="redis://invalid-host:9999")
        await client.connect()
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_set_get_memory(self):
        client = RedisClient()
        await client.set("key1", "value1")
        result = await client.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_none(self):
        client = RedisClient()
        result = await client.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_memory(self):
        client = RedisClient()
        await client.set("del_key", "del_val")
        count = await client.delete("del_key")
        assert count == 1
        assert await client.get("del_key") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self):
        client = RedisClient()
        count = await client.delete("ghost")
        assert count == 0

    @pytest.mark.asyncio
    async def test_xadd_memory(self):
        client = RedisClient()
        msg_id = await client.xadd("events", {"type": "test", "value": "42"})
        assert isinstance(msg_id, str)
        assert "-" in msg_id

    @pytest.mark.asyncio
    async def test_xread_memory(self):
        client = RedisClient()
        await client.xadd("stream1", {"event": "created"})
        await client.xadd("stream1", {"event": "updated"})
        results = await client.xread({"stream1": "0"})
        assert len(results) == 1
        stream_name, messages = results[0]
        assert stream_name == "stream1"
        assert len(messages) == 2
        assert messages[0][1]["event"] == "created"
        assert messages[1][1]["event"] == "updated"

    @pytest.mark.asyncio
    async def test_xread_with_last_id(self):
        client = RedisClient()
        id1 = await client.xadd("s", {"n": "1"})
        await client.xadd("s", {"n": "2"})
        results = await client.xread({"s": id1})
        assert len(results) == 1
        _, messages = results[0]
        assert len(messages) == 1
        assert messages[0][1]["n"] == "2"

    @pytest.mark.asyncio
    async def test_xread_empty_stream(self):
        client = RedisClient()
        results = await client.xread({"empty": "0"})
        assert results == []
