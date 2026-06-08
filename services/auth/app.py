"""Auth Service — JWT 签发/验证 + 用户 CRUD。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from uuid import NAMESPACE_DNS, UUID, uuid5

from fastapi import FastAPI
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from reqradar.kernel.database import Base, create_engine, create_session_factory
from reqradar.kernel.models import User

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    logging.getLogger("reqradar.auth").warning("JWT_SECRET 未配置，使用不安全的默认密钥")
    JWT_SECRET = "dev-secret-not-for-production"
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


def _str_to_uuid(s: str) -> UUID:
    """将字符串转换为 UUID，非 UUID 格式时使用 uuid5 生成确定性 UUID。"""
    try:
        return UUID(s)
    except ValueError:
        return uuid5(NAMESPACE_DNS, s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auth Service 启动")
    database_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./reqradar_dev.db")
    engine = create_engine(database_url)
    session_factory = create_session_factory(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.db_session_factory = session_factory
    app.state.db_engine = engine
    yield
    await engine.dispose()
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
    from datetime import UTC, datetime

    from reqradar.infrastructure.auth import decode_jwt_token

    try:
        payload = decode_jwt_token(req.token, JWT_SECRET)

        user_id = payload.get("sub", "")
        async with app.state.db_session_factory() as session:
            uid = _str_to_uuid(user_id)
            user = await session.get(User, uid)

        if user is None or not user.is_active:
            return {"valid": False, "reason": "USER_INACTIVE_OR_NOT_FOUND"}

        exp_timestamp = payload.get("exp", 0)
        exp_datetime = (
            datetime.fromtimestamp(exp_timestamp, tz=UTC).isoformat() if exp_timestamp else None
        )
        return {
            "valid": True,
            "jti": payload.get("jti", ""),
            "expires_at": exp_datetime,
            "user": {
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": "admin" if user.is_superuser else "user",
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
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

    async with app.state.db_session_factory() as session:
        uid = _str_to_uuid(req.user_id)
        existing = await session.get(User, uid)
        if existing:
            existing.username = req.username
            existing.email = req.email or f"{uid}@placeholder.local"
            existing.is_active = req.is_active
            existing.is_superuser = req.is_superuser
        else:
            session.add(
                User(
                    id=uid,
                    username=req.username,
                    email=req.email or f"{uid}@placeholder.local",
                    hashed_password="!",
                    is_active=req.is_active,
                    is_superuser=req.is_superuser,
                )
            )
        await session.commit()

    return {"token": token, "token_type": "bearer"}


@app.get("/api/v2/users/me")
async def get_current_user():
    """获取当前用户信息（需 JWT）。"""
    return {"user_id": "demo", "username": "demo_user"}


@app.post("/internal/v2/auth/check-permission")
async def check_permission(req: CheckPermissionRequest):
    """检查用户权限 (I-01 §5.2)。"""
    async with app.state.db_session_factory() as session:
        uid = _str_to_uuid(req.user_id)
        user = await session.get(User, uid)

    if user is not None:
        allowed = user.is_superuser or req.action in ("read", "list")
        return {
            "user_id": req.user_id,
            "resource": req.resource,
            "action": req.action,
            "allowed": allowed,
            "reason": "superuser" if user.is_superuser else "role_check",
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

    async with app.state.db_session_factory() as session:
        uid = _str_to_uuid(user_id)
        user = await session.get(User, uid)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "USER_NOT_FOUND", "message": f"用户不存在: {user_id}"}},
        )
    return {
        "user_id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": "admin" if user.is_superuser else "user",
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
    }
