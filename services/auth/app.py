"""Auth Service — JWT 签发/验证 + 用户 CRUD。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auth Service 启动")
    yield
    logger.info("Auth Service 关闭")


app = FastAPI(
    title="ReqRadar Auth Service",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth"}


@app.post("/internal/v2/auth/verify")
async def verify_token(req: VerifyRequest):
    """验证 JWT Token，返回用户信息。"""
    from reqradar.infrastructure.auth import decode_jwt_token

    try:
        payload = decode_jwt_token(req.token, JWT_SECRET)
        return {
            "valid": True,
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
        return {"valid": False, "error": str(e)}


@app.post("/internal/v2/auth/issue")
async def issue_token(req: IssueRequest):
    """签发 JWT Token。"""
    from reqradar.infrastructure.auth import create_jwt_token

    token = create_jwt_token(
        user_id=req.user_id,
        username=req.username,
        is_superuser=req.is_superuser,
        secret=JWT_SECRET,
    )
    return {"token": token, "token_type": "bearer"}


@app.get("/api/v2/users/me")
async def get_current_user():
    """获取当前用户信息（需 JWT）。"""
    return {"user_id": "demo", "username": "demo_user"}
