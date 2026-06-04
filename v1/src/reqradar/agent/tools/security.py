import fnmatch
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("reqradar.agent.security")

DEFAULT_SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.crt",
    "secrets/",
    "credentials/",
    ".aws/",
    ".ssh/",
]


class ToolPermissionChecker:
    def __init__(self, user_permissions: set[str] | None = None):
        self.user_permissions = user_permissions or set()

    def is_allowed(self, permission: str) -> bool:
        return permission in self.user_permissions

    def check_tool(self, tool_permissions: list[str]) -> tuple[bool, list[str]]:
        missing = [p for p in tool_permissions if p not in self.user_permissions]
        return len(missing) == 0, missing


def check_tool_permissions(required_permissions: list[str], user_permissions: set[str]) -> bool:
    checker = ToolPermissionChecker(user_permissions)
    allowed, missing = checker.check_tool(required_permissions)
    if not allowed:
        logger.warning("Tool permission denied. Missing: %s", missing)
    return allowed


class PathSandbox:
    def __init__(self, allowed_root: str):
        self.allowed_root = Path(allowed_root).resolve()

    def is_allowed(self, file_path: str) -> bool:
        try:
            resolved = Path(file_path).resolve()
            try:
                resolved.relative_to(self.allowed_root)
                return True
            except ValueError:
                return False
        except (OSError, ValueError):
            return False

    def normalize(self, file_path: str) -> str:
        return str(Path(file_path).resolve())


class SensitiveFileFilter:
    def __init__(self, extra_patterns: list[str] | None = None):
        self.patterns = list(DEFAULT_SENSITIVE_PATTERNS)
        if extra_patterns:
            self.patterns.extend(extra_patterns)

    def is_sensitive(self, file_path: str) -> bool:
        path = Path(file_path)
        name = path.name
        parts = path.parts
        for pattern in self.patterns:
            if pattern.endswith("/"):
                if any(part == pattern.rstrip("/") for part in parts):
                    return True
            else:
                if fnmatch.fnmatch(name, pattern):
                    return True
                if fnmatch.fnmatch(str(path), pattern):
                    return True
        return False
