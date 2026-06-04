"""Auth Service — JWT 签发/验证 + 用户 CRUD。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key")


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


@app.get("/internal/v2/auth/verify")
async def verify_token(token: str = ""):
    """验证 JWT Token，返回用户信息。"""
    from reqradar.infrastructure.auth import decode_jwt_token

    try:
        payload = decode_jwt_token(token, JWT_SECRET)
        return {"valid": True, "user": payload}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.post("/internal/v2/auth/issue")
async def issue_token(user_id: str, username: str, is_superuser: bool = False):
    """签发 JWT Token。"""
    from reqradar.infrastructure.auth import create_jwt_token

    token = create_jwt_token(
        user_id=user_id,
        username=username,
        is_superuser=is_superuser,
        secret=JWT_SECRET,
    )
    return {"token": token, "token_type": "bearer"}


@app.get("/api/v2/users/me")
async def get_current_user():
    """获取当前用户信息（需 JWT）。"""
    return {"user_id": "demo", "username": "demo_user"}
