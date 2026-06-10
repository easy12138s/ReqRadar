"""端到端测试 fixture。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _set_e2e_env(monkeypatch):
    """设置 E2E 测试环境变量。"""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing")
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")
    monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite://")


@pytest.fixture
def e2e_db_url(tmp_path):
    """E2E 测试专用 SQLite 数据库 URL。"""
    return "sqlite+aiosqlite:///%s" % (tmp_path / "e2e_test.db")


@pytest.fixture
def e2e_mock_llm_client():
    """E2E 专用 Mock LLM 客户端。"""
    client = AsyncMock()
    client.complete = AsyncMock(return_value="E2E Mock LLM response")
    client.complete_structured = AsyncMock(return_value={"result": "e2e_mock"})
    client.complete_with_tools = AsyncMock(
        return_value={"choices": [{"message": {"content": "e2e_mock"}}]}
    )
    client.supports_tool_calling = AsyncMock(return_value=True)
    client.estimate_tokens = MagicMock(return_value=100)
    return client


@pytest.fixture
def e2e_auth_token():
    """E2E 测试用 JWT token（mock）。"""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token"


@pytest.fixture
def e2e_project_id():
    """E2E 测试用项目 ID。"""
    import uuid

    return str(uuid.uuid4())
