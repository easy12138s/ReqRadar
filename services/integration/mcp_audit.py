"""MCP 审计日志 — 工具调用记录与敏感信息脱敏。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

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

    def __init__(self, max_entries: int = 10000, retention_hours: int = 72) -> None:
        self._entries: list[AuditEntry] = []
        self._max_entries = max_entries
        self._retention_hours = retention_hours
        self._db_session_factory = None

    def set_session_factory(self, factory):
        self._db_session_factory = factory

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
        # PG 持久化
        if self._db_session_factory:
            try:
                from reqradar.kernel.models import MCPToolCall

                session = self._db_session_factory()
                session.add(
                    MCPToolCall(
                        id=entry.entry_id,
                        access_key_id=entry.key_id or "",
                        tool_name=entry.tool_name,
                        arguments_json=entry.sanitized_arguments,
                        result_summary=entry.result_summary[:500],
                        duration_ms=entry.duration_ms,
                        success=True,
                    )
                )
                session.commit()
                session.close()
            except Exception as e:
                logger.warning("MCP audit PG 持久化失败: %s", e)
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

    def cleanup(self, retention_hours: int | float | None = None) -> int:
        """清理过期审计日志。

        Args:
            retention_hours: 保留时间（小时），None 使用默认值

        Returns:
            清除的条数
        """
        hours = retention_hours if retention_hours is not None else self._retention_hours
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.timestamp >= cutoff]
        removed = before - len(self._entries)
        if removed > 0:
            logger.info("审计日志清理: 删除 %d 条过期记录", removed)
        return removed
