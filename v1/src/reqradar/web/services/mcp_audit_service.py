import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import MCPToolCall

logger = logging.getLogger("reqradar.mcp_audit")

SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "token",
        "api_key",
        "key",
        "password",
        "secret",
    }
)


def sanitize_args(arguments: dict) -> dict:
    sanitized: dict = {}
    for k, v in arguments.items():
        if k.lower() in SENSITIVE_KEYS:
            sanitized[k] = "***REDACTED***"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_args(v)
        elif isinstance(v, list):
            sanitized[k] = [sanitize_args(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = v
    return sanitized


async def record_call(
    db: AsyncSession,
    access_key_id: int | None,
    tool_name: str,
    arguments: dict,
    result_summary: str,
    duration_ms: int,
    success: bool = True,
    error_message: str | None = None,
) -> MCPToolCall:
    cleaned = sanitize_args(arguments)
    row = MCPToolCall(
        access_key_id=access_key_id,
        tool_name=tool_name,
        arguments_json=cleaned,
        result_summary=result_summary,
        duration_ms=duration_ms,
        success=success,
        error_message=error_message,
    )
    db.add(row)
    await db.flush()
    return row


async def query_calls(
    db: AsyncSession,
    access_key_id: int | None = None,
    tool_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MCPToolCall]:
    stmt = select(MCPToolCall).order_by(MCPToolCall.created_at.desc())
    if access_key_id is not None:
        stmt = stmt.where(MCPToolCall.access_key_id == access_key_id)
    if tool_name is not None:
        stmt = stmt.where(MCPToolCall.tool_name == tool_name)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def cleanup_expired(db: AsyncSession, retention_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    stmt = delete(MCPToolCall).where(MCPToolCall.created_at < cutoff)
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount  # type: ignore[attr-defined,no-any-return]
