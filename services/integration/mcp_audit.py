"""MCP 审计日志 — 工具调用记录与敏感信息脱敏。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_SENSITIVE_KEYWORDS = frozenset(
    {
        "token",
        "password",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "credential",
        "private_key",
    }
)

_REDACTED = "***REDACTED***"


def sanitize_arguments(args: dict) -> dict:
    """递归脱敏字典中的敏感字段。"""
    result: dict = {}
    for k, v in args.items():
        if any(kw in k.lower() for kw in _SENSITIVE_KEYWORDS):
            result[k] = _REDACTED
        elif isinstance(v, dict):
            result[k] = sanitize_arguments(v)
        elif isinstance(v, list):
            result[k] = [sanitize_arguments(i) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


@dataclass
class AuditEntry:
    """单条审计日志。"""

    entry_id: str
    tool_name: str
    sanitized_arguments: dict
    result_summary: str
    duration_ms: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    key_id: str = ""
    key_name: str = ""


class AuditLog:
    """MCP 审计日志（内存模式，P3 后迁移到 PG）。"""

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: list[AuditEntry] = []
        self._max_entries = max_entries

    def clear(self) -> None:
        self._entries.clear()

    def record(
        self,
        tool_name: str,
        arguments: dict,
        result_summary: str,
        duration_ms: int,
        key_id: str = "",
        key_name: str = "",
    ) -> AuditEntry:
        """记录一次工具调用。"""
        import secrets

        entry = AuditEntry(
            entry_id=secrets.token_hex(8),
            tool_name=tool_name,
            sanitized_arguments=sanitize_arguments(arguments),
            result_summary=result_summary,
            duration_ms=duration_ms,
            key_id=key_id,
            key_name=key_name,
        )
        self._entries.append(entry)
        logger.info("审计记录: tool=%s, duration=%dms", tool_name, duration_ms)
        return entry

    def query(
        self,
        tool_name: str | None = None,
        key_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询审计日志。"""
        filtered = self._entries
        if tool_name is not None:
            filtered = [e for e in filtered if e.tool_name == tool_name]
        if key_id is not None:
            filtered = [e for e in filtered if e.key_id == key_id]
        return [
            {
                "entry_id": e.entry_id,
                "tool_name": e.tool_name,
                "sanitized_arguments": e.sanitized_arguments,
                "result_summary": e.result_summary,
                "duration_ms": e.duration_ms,
                "timestamp": e.timestamp.isoformat(),
                "key_id": e.key_id,
                "key_name": e.key_name,
            }
            for e in filtered[-limit:]
        ]

    def cleanup(self) -> int:
        """清理全部审计日志，返回清除条数。"""
        count = len(self._entries)
        self._entries.clear()
        logger.info("审计日志已清理: %d 条", count)
        return count
