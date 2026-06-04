from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from reqradar.infrastructure.config import MCPConfig
from reqradar.web.dependencies import CurrentUser, DbSession
from reqradar.web.models import MCPAccessKey, MCPToolCall
from reqradar.web.services.mcp_audit_service import cleanup_expired, query_calls
from reqradar.web.services.mcp_auth_service import (
    generate_key,
    list_keys,
    re_export_key,
    revoke_key,
)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class CreateKeyRequest(BaseModel):
    name: str
    scopes: list[str] = Field(default_factory=lambda: ["read"])


class MCPConfigUpdate(BaseModel):
    enabled: bool | None = None
    auto_start_with_web: bool | None = None
    host: str | None = None
    port: int | None = None
    path: str | None = None
    public_url: str | None = None
    audit_enabled: bool | None = None
    audit_retention_days: int | None = None


def _key_to_dict(key: MCPAccessKey) -> dict:
    return {
        "id": key.id,
        "user_id": key.user_id,
        "key_prefix": key.key_prefix,
        "name": key.name,
        "scopes": key.scopes,
        "is_active": key.is_active,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
        "created_at": key.created_at.isoformat() if key.created_at else None,
    }


def _tool_call_to_dict(call: MCPToolCall) -> dict:
    return {
        "id": call.id,
        "access_key_id": call.access_key_id,
        "tool_name": call.tool_name,
        "arguments_json": call.arguments_json,
        "result_summary": call.result_summary,
        "duration_ms": call.duration_ms,
        "success": call.success,
        "error_message": call.error_message,
        "created_at": call.created_at.isoformat() if call.created_at else None,
    }


@router.get("/config")
async def get_config(request: Request, current_user: CurrentUser):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return request.app.state.config.mcp.model_dump()


@router.put("/config")
async def update_config(
    request: Request,
    body: MCPConfigUpdate,
    current_user: CurrentUser,
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    mcp: MCPConfig = request.app.state.config.mcp
    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(mcp, field, value)
    return mcp.model_dump()


@router.get("/keys")
async def get_keys(db: DbSession, current_user: CurrentUser):
    if current_user.role == "admin":
        stmt = select(MCPAccessKey).order_by(MCPAccessKey.created_at.desc())
        result = await db.execute(stmt)
        keys = list(result.scalars().all())
    else:
        keys = await list_keys(db, current_user.id)
    return [_key_to_dict(k) for k in keys]


@router.post("/keys", status_code=status.HTTP_201_CREATED)
async def create_key(
    request: Request,
    body: CreateKeyRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    mcp_config = request.app.state.config.mcp
    mcp_result = await generate_key(db, current_user.id, body.name, body.scopes, mcp_config)
    return mcp_result


@router.post("/keys/{key_id}/revoke")
async def revoke_key_endpoint(
    key_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role == "admin":
        key = await db.get(MCPAccessKey, key_id)
        if key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
        revoked = await revoke_key(db, key_id, key.user_id)
    else:
        revoked = await revoke_key(db, key_id, current_user.id)
    if revoked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    return _key_to_dict(revoked)


@router.post("/keys/{key_id}/re-export")
async def re_export_key_endpoint(
    key_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    mcp_config = request.app.state.config.mcp
    if current_user.role == "admin":
        key = await db.get(MCPAccessKey, key_id)
        if key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
        result = await re_export_key(db, key_id, key.user_id, mcp_config)
    else:
        result = await re_export_key(db, key_id, current_user.id, mcp_config)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    return result


@router.get("/tool-calls")
async def get_tool_calls(
    db: DbSession,
    current_user: CurrentUser,
    access_key_id: int | None = None,
    tool_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    calls = await query_calls(
        db, access_key_id=access_key_id, tool_name=tool_name, limit=limit, offset=offset
    )
    return [_tool_call_to_dict(c) for c in calls]


@router.post("/audit/cleanup")
async def audit_cleanup(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    retention_days = request.app.state.config.mcp.audit_retention_days
    deleted = await cleanup_expired(db, retention_days)
    return {"deleted": deleted}
