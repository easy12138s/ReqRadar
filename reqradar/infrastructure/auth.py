"""JWT 认证模块 — Token 签发与校验。

支持 PyJWT（生产）和内置 mock token（PyJWT 不可用时的降级方案）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

_HAS_PYJWT = False
try:
    import jwt as _jwt

    _HAS_PYJWT = True
except ImportError:
    _jwt = None  # type: ignore[assignment]

_MOCK_SECRET = os.environ.get("JWT_SECRET", "reqradar-mock-secret-key")


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _mock_sign(payload_str: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()[:32]


def create_mock_token(payload: dict, secret: str) -> str:
    """创建内置 mock token（不依赖 PyJWT）。"""
    payload_str = json.dumps(payload, separators=(",", ":"))
    sig = _mock_sign(payload_str, secret or _MOCK_SECRET)
    return f"mock.{_b64_encode(payload_str.encode())}.{sig}"


def decode_mock_token(token: str, secret: str) -> dict:
    """解码内置 mock token。"""
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "mock":
        raise ValueError("无效的 mock token 格式")
    _, payload_b64, sig = parts
    payload_str = _b64_decode(payload_b64).decode("utf-8")
    expected_sig = _mock_sign(payload_str, secret or _MOCK_SECRET)
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("mock token 签名验证失败")
    payload = json.loads(payload_str)
    if payload.get("exp") and payload["exp"] < time.time():
        raise ValueError("token 已过期")
    return payload


def create_jwt_token(
    user_id: str,
    username: str,
    secret: str = "",
    expires_seconds: int = 7200,
    use_mock: bool = False,
) -> str:
    """创建 JWT Token。

    Args:
        user_id: 用户唯一标识。
        username: 用户名。
        secret: 签名密钥。为空时使用内置 mock 密钥。
        expires_seconds: 过期时间（秒）。
        use_mock: 强制使用 mock token（忽略 PyJWT）。

    Returns:
        签发的 Token 字符串。
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + expires_seconds,
    }

    if use_mock or not _HAS_PYJWT:
        return create_mock_token(payload, secret)

    return _jwt.encode(payload, secret, algorithm="HS256")  # type: ignore[no-any-return]


def decode_jwt_token(token: str, secret: str = "", use_mock: bool = False) -> dict:
    """解码并验证 JWT Token。

    Args:
        token: 待解码的 Token 字符串。
        secret: 签名密钥。
        use_mock: 强制使用 mock 解码（忽略 PyJWT）。

    Returns:
        解码后的 payload 字典，至少包含 sub、username、iat、exp 字段。

    Raises:
        ValueError: Token 无效、已过期或签名错误。
    """
    try:
        if use_mock or not _HAS_PYJWT:
            return decode_mock_token(token, secret)

        return _jwt.decode(token, secret, algorithms=["HS256"])  # type: ignore[no-any-return]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"token 解码失败: {exc}") from exc
