"""Auth Service — JWT 签发/验证 + 用户 CRUD。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")


class VerifyRequest(BaseModel):
    """JWT 验证请求。"""

    token: str = Field(description="JWT Token 字符串")


class IssueRequest(BaseModel):
    """JWT 签发请求。"""

    user_id: str = Field(description="用户 ID")
    username: str = Field(description="用户名")
    email: str = Field(default="", description="用户邮箱")
    role: str = Field(default="user", description="用户角色")
    is_active: bool = Field(default=True, description="是否激活")
    is_superuser: bool = Field(default=False, description="是否超级用户")


class CheckPermissionRequest(BaseModel):
    """权限检查请求。"""

    user_id: str = Field(description="用户 ID")
    resource: str = Field(description="资源路径")
    action: str = Field(description="操作类型")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auth Service 启动")
    app.state._users = {}
    yield
    logger.info("Auth Service 关闭")


app = FastAPI(
    title="ReqRadar Auth Service",
    version="2.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def verify_internal_api_key(request, call_next):
    """校验入站请求的 X-Internal-API-Key 头。"""
    if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    api_key = request.headers.get("X-Internal-API-Key", "")
    if api_key != INTERNAL_API_KEY:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "UNAUTHORIZED", "message": "Invalid Internal API Key"}},
        )
    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth"}


@app.post("/internal/v2/auth/verify")
async def verify_token(req: VerifyRequest):
    """验证 JWT Token，返回用户信息。"""
    from reqradar.infrastructure.auth import decode_jwt_token

    try:
        payload = decode_jwt_token(req.token, JWT_SECRET)
        from datetime import UTC, datetime

        exp_timestamp = payload.get("exp", 0)
        exp_datetime = (
            datetime.fromtimestamp(exp_timestamp, tz=UTC).isoformat() if exp_timestamp else None
        )
        return {
            "valid": True,
            "jti": payload.get("jti", ""),
            "expires_at": exp_datetime,
            "user": {
                "user_id": payload.get("sub", ""),
                "username": payload.get("username", ""),
                "email": payload.get("email", ""),
                "role": payload.get("role", "user"),
                "is_active": payload.get("is_active", True),
                "is_superuser": payload.get("is_superuser", False),
            },
        }
    except Exception as e:
        reason = "TOKEN_UNKNOWN"
        error_msg = str(e)
        if "expired" in error_msg.lower():
            reason = "TOKEN_EXPIRED"
        elif "invalid" in error_msg.lower():
            reason = "TOKEN_INVALID"
        elif "decode" in error_msg.lower() or "malformed" in error_msg.lower():
            reason = "TOKEN_MALFORMED"
        return {"valid": False, "reason": reason}


@app.post("/internal/v2/auth/issue")
async def issue_token(req: IssueRequest):
    """签发 JWT Token。"""
    from reqradar.infrastructure.auth import create_jwt_token

    token = create_jwt_token(
        user_id=req.user_id,
        username=req.username,
        secret=JWT_SECRET,
    )
    app.state._users[req.user_id] = {
        "username": req.username,
        "email": req.email,
        "role": req.role,
        "is_active": req.is_active,
        "is_superuser": req.is_superuser,
    }
    return {"token": token, "token_type": "bearer"}


@app.get("/api/v2/users/me")
async def get_current_user():
    """获取当前用户信息（需 JWT）。"""
    return {"user_id": "demo", "username": "demo_user"}


@app.post("/internal/v2/auth/check-permission")
async def check_permission(req: CheckPermissionRequest):
    """检查用户权限 (I-01 §5.2)。"""

    _users = app.state._users
    # 从已知用户中查找
    for uid, u in _users.items():
        if uid == req.user_id:
            allowed = u.get("is_superuser", False) or req.action in ("read", "list")
            return {
                "user_id": req.user_id,
                "resource": req.resource,
                "action": req.action,
                "allowed": allowed,
                "reason": "superuser" if u.get("is_superuser") else "role_check",
            }
    return {
        "user_id": req.user_id,
        "resource": req.resource,
        "action": req.action,
        "allowed": False,
        "reason": "user_not_found",
    }


@app.get("/internal/v2/users/{user_id}")
async def get_user(user_id: str):
    """查询用户信息 (I-01 §5.3)。"""
    from fastapi import HTTPException

    _users = app.state._users
    u = _users.get(user_id)
    if u is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "USER_NOT_FOUND", "message": f"用户不存在: {user_id}"}},
        )
    return {
        "user_id": user_id,
        "username": u.get("username", ""),
        "email": u.get("email", ""),
        "role": u.get("role", "user"),
        "is_active": u.get("is_active", True),
        "is_superuser": u.get("is_superuser", False),
    }
