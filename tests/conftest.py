"""共享测试 fixture。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def tmp_db_url(tmp_path):
    """临时 SQLite 数据库 URL。"""
    return "sqlite+aiosqlite:///%s" % (tmp_path / "test.db")


@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端。"""
    client = AsyncMock()
    client.complete = AsyncMock(return_value="Mock LLM response")
    client.complete_structured = AsyncMock(return_value={"result": "mock"})
    client.complete_with_tools = AsyncMock(
        return_value={"choices": [{"message": {"content": "mock"}}]}
    )
    client.supports_tool_calling = AsyncMock(return_value=True)
    client.estimate_tokens = MagicMock(return_value=100)
    return client


@pytest.fixture
def mock_redis():
    """Mock Redis 客户端。"""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.xadd = AsyncMock(return_value="1-0")
    redis.xread = AsyncMock(return_value=[])
    redis.close = AsyncMock()
    return redis


@pytest.fixture
def env_jwt_secret(monkeypatch):
    """设置 JWT_SECRET 环境变量。"""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing")


@pytest.fixture
def env_internal_key(monkeypatch):
    """设置 INTERNAL_API_KEY 环境变量。"""
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")
