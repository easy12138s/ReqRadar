"""集成测试 fixture。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """设置测试环境变量。"""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing")
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")
    monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite://")


@pytest.fixture
def integration_db_url(tmp_path):
    """集成测试专用 SQLite 数据库 URL。"""
    return "sqlite+aiosqlite:///%s" % (tmp_path / "integration_test.db")


@pytest.fixture
def mock_llm_client():
    """集成测试 Mock LLM 客户端。"""
    client = AsyncMock()
    client.complete = AsyncMock(return_value="Mock LLM response for integration test")
    client.complete_structured = AsyncMock(return_value={"result": "mock"})
    client.complete_with_tools = AsyncMock(
        return_value={"choices": [{"message": {"content": "mock"}}]}
    )
    client.supports_tool_calling = AsyncMock(return_value=True)
    client.estimate_tokens = MagicMock(return_value=100)
    return client
