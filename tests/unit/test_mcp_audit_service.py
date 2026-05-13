"""MCP 审计服务单元测试"""

import pytest
from unittest.mock import MagicMock

from reqradar.web.services.mcp_audit_service import SENSITIVE_KEYS, sanitize_args


class TestSanitizeArgs:
    def test_no_sensitive_keys(self):
        args = {"name": "test", "value": 123}
        result = sanitize_args(args)
        assert result == args

    def test_redacts_authorization(self):
        args = {"authorization": "Bearer secret_token"}
        result = sanitize_args(args)
        assert result["authorization"] == "***REDACTED***"

    def test_redacts_all_sensitive_keys(self):
        for key in ["token", "api_key", "password", "secret"]:
            args = {key: "sensitive_value"}
            result = sanitize_args(args)
            assert result[key] == "***REDACTED***", f"Failed to redact {key}"

    def test_case_insensitive_matching(self):
        args = {"Authorization": "Bearer token", "API_KEY": "key123"}
        result = sanitize_args(args)
        assert result["Authorization"] == "***REDACTED***"
        assert result["API_KEY"] == "***REDACTED***"

    def test_recursive_dict_sanitization(self):
        args = {"nested": {"token": "hidden"}}
        result = sanitize_args(args)
        assert result["nested"]["token"] == "***REDACTED***"

    def test_list_of_dicts_sanitization(self):
        args = {"items": [{"key": "val1"}, {"password": "secret"}]}
        result = sanitize_args(args)
        assert result["items"][1]["password"] == "***REDACTED***"

    def test_preserves_non_sensitive_values(self):
        args = {
            "query": "search term",
            "project_id": 5,
            "limit": 10,
            "normal_key": "normal_value",
        }
        result = sanitize_args(args)
        for k, v in args.items():
            if k.lower() not in SENSITIVE_KEYS:
                assert result[k] == v
