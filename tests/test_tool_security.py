import pytest
from reqradar.agent.tools.security import ToolPermissionChecker, PathSandbox, SensitiveFileFilter, check_tool_permissions


def test_permission_checker_allow():
    checker = ToolPermissionChecker(user_permissions={"read:code", "read:memory"})
    assert checker.is_allowed("read:code")
    assert checker.is_allowed("read:memory")


def test_permission_checker_deny():
    checker = ToolPermissionChecker(user_permissions={"read:code"})
    assert not checker.is_allowed("write:report")
    assert not checker.is_allowed("read:user_memory")


def test_path_sandbox_allow():
    sandbox = PathSandbox(allowed_root="/home/user/project")
    assert sandbox.is_allowed("/home/user/project/src/app.py")
    assert sandbox.is_allowed("/home/user/project/web/models.py")


def test_path_sandbox_deny_traversal():
    sandbox = PathSandbox(allowed_root="/home/user/project")
    assert not sandbox.is_allowed("/home/user/project/../etc/passwd")
    assert not sandbox.is_allowed("/home/user/project/../../etc/passwd")


def test_path_sandbox_deny_outside():
    sandbox = PathSandbox(allowed_root="/home/user/project")
    assert not sandbox.is_allowed("/etc/passwd")
    assert not sandbox.is_allowed("/home/user/other/file.py")


def test_sensitive_file_filter_default():
    sf = SensitiveFileFilter()
    assert sf.is_sensitive(".env")
    assert sf.is_sensitive("secrets/database.key")
    assert sf.is_sensitive("config/cert.pem")
    assert not sf.is_sensitive("src/app.py")
    assert not sf.is_sensitive("README.md")


def test_sensitive_file_filter_custom():
    sf = SensitiveFileFilter(extra_patterns=["*.private"])
    assert sf.is_sensitive("data.private")
    assert not sf.is_sensitive("data.csv")


def test_permission_checker_with_tool():
    mock_tool_permissions = {"read:code", "read:memory", "read:git"}
    allowed = check_tool_permissions(
        required_permissions=["read:code", "read:memory"],
        user_permissions=mock_tool_permissions,
    )
    assert allowed is True


def test_permission_checker_tool_denied():
    mock_tool_permissions = {"read:code"}
    allowed = check_tool_permissions(
        required_permissions=["read:code", "write:report"],
        user_permissions=mock_tool_permissions,
    )
    assert allowed is False
