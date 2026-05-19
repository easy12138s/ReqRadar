"""认证辅助工具 — 提供统一的测试用户创建、登录、Token 生成。"""

from __future__ import annotations

from reqradar.web.api.auth import create_access_token, hash_password
from reqradar.web.models import User


def make_user_payload(
    email: str = "testuser@example.com",
    password: str = "Password123",
    display_name: str = "Test User",
    role: str = "user",
) -> dict:
    return {
        "email": email,
        "password": password,
        "display_name": display_name,
        "role": role,
    }


def make_auth_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def make_bearer_token(user_id: int) -> str:
    return create_access_token(user_id)
