"""MCP 认证模块单元测试"""

import pytest

from reqradar.mcp.auth import MCPAuthResult, authenticate_mcp_request, parse_bearer_token


class TestParseBearerToken:
    def test_valid_bearer_token(self):
        token = parse_bearer_token("Bearer rr_mcp_abc123")
        assert token == "rr_mcp_abc123"

    def test_missing_auth_header(self):
        assert parse_bearer_token(None) is None

    def test_empty_string(self):
        assert parse_bearer_token("") is None

    def test_wrong_scheme(self):
        assert parse_bearer_token("Basic abc123") is None

    def test_no_prefix(self):
        token = "rr_mcp_xyz"
        result = parse_bearer_token(token)
        assert result is None

    def test_case_insensitive_bearer(self):
        token = parse_bearer_token("bearer rr_mcp_test")
        assert token == "rr_mcp_test"

    def test_non_rr_mcp_prefix(self):
        assert parse_bearer_token("Bearer other_token") is None


class TestMCPAuthResult:
    def test_creation(self):
        from unittest.mock import MagicMock

        key = MagicMock()
        key.id = 1
        key.user_id = 10
        key.scopes = ["read"]
        result = MCPAuthResult(access_key=key, key_id=1, user_id=10, scopes=["read"])
        assert result.key_id == 1
        assert result.user_id == 10
        assert result.scopes == ["read"]


class TestAuthenticateMCPRequest:
    @pytest.mark.asyncio
    async def test_null_header_returns_none(self):
        from unittest.mock import AsyncMock

        db = AsyncMock()
        result = await authenticate_mcp_request(None, db)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_format_returns_none(self):
        from unittest.mock import AsyncMock

        db = AsyncMock()
        result = await authenticate_mcp_request("Basic abc", db)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self):
        from unittest.mock import AsyncMock, patch

        db = AsyncMock()
        with patch("reqradar.mcp.auth.verify_key", return_value=None):
            result = await authenticate_mcp_request("Bearer rr_mcp_fake", db)
            assert result is None

    @pytest.mark.asyncio
    async def test_valid_key_returns_result(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        db = AsyncMock()
        mock_key = MagicMock()
        mock_key.id = 5
        mock_key.user_id = 3
        mock_key.scopes = ["read"]

        with patch("reqradar.mcp.auth.verify_key", return_value=mock_key) as mock_verify:
            result = await authenticate_mcp_request("Bearer rr_mcp_real", db)
            assert result is not None
            assert result.key_id == 5
            assert result.user_id == 3
            mock_verify.assert_called_once_with(db, "rr_mcp_real")
