"""MCP 访问密钥管理 — 生成、验证、撤销 API Key。"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime

try:
    import bcrypt

    _HAS_BCRYPT = True
except ImportError:
    import hashlib

    _HAS_BCRYPT = False

logger = logging.getLogger(__name__)

_KEY_PREFIX = "rr_mcp_"


@dataclass
class AccessKey:
    """MCP 访问密钥元数据（不存储原始密钥）。"""

    key_id: str
    name: str
    key_hash: str
    scopes: list[str] = field(default_factory=lambda: ["read"])
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None

    @property
    def revoked(self) -> bool:
        return self.status == "revoked"


class KeyManager:
    """MCP 密钥管理器 — 内存模式，P3 后迁移到 PG。"""

    def __init__(self) -> None:
        self._keys: dict[str, AccessKey] = {}
        self._db_session_factory = None

    def set_session_factory(self, factory):
        self._db_session_factory = factory

    def clear(self) -> None:
        self._keys.clear()

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        if _HAS_BCRYPT:
            return bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def generate_key(self, name: str, scopes: list[str] | None = None) -> tuple[str, AccessKey]:
        """生成新 MCP 访问密钥，返回 (原始密钥, AccessKey 元数据)。"""
        token = secrets.token_urlsafe(32)
        raw_key = f"{_KEY_PREFIX}{token}"
        ak = AccessKey(
            key_id=secrets.token_hex(8),
            name=name,
            key_hash=self._hash_key(raw_key),
            scopes=scopes or ["read"],
        )
        self._keys[ak.key_id] = ak
        # PG 持久化
        if self._db_session_factory:
            session = None
            try:
                from reqradar.kernel.models import MCPAccessKey

                session = self._db_session_factory()
                session.add(
                    MCPAccessKey(
                        id=ak.key_id,
                        user_id="",
                        key_prefix="rr_mcp_",
                        key_hash=ak.key_hash,
                        name=ak.name,
                        scopes=ak.scopes,
                        is_active=True,
                        created_at=ak.created_at,
                    )
                )
                session.commit()
            except Exception as e:
                logger.warning("MCPKey PG 持久化失败: %s", e)
            finally:
                if session:
                    session.close()
        logger.info("MCP 密钥已生成: name=%s, key_id=%s", name, ak.key_id)
        return raw_key, ak

    def verify_key(self, raw_key: str) -> AccessKey | None:
        """验证原始密钥，返回 AccessKey 或 None。"""
        if not raw_key.startswith(_KEY_PREFIX):
            return None
        for ak in self._keys.values():
            if ak.revoked:
                continue
            if _HAS_BCRYPT:
                if bcrypt.checkpw(raw_key.encode(), ak.key_hash.encode()):
                    ak.last_used_at = datetime.now(UTC)
                    return ak
            else:
                if hashlib.sha256(raw_key.encode()).hexdigest() == ak.key_hash:
                    ak.last_used_at = datetime.now(UTC)
                    return ak
        return None

    def revoke_key(self, key_id: str) -> bool:
        """撤销密钥。返回是否成功。"""
        ak = self._keys.get(key_id)
        if ak is None or ak.status == "revoked":
            return False
        ak.status = "revoked"
        ak.revoked_at = datetime.now(UTC)
        # PG 持久化
        if self._db_session_factory:
            session = None
            try:
                from reqradar.kernel.models import MCPAccessKey

                session = self._db_session_factory()
                ak_db = session.query(MCPAccessKey).filter_by(id=key_id).first()
                if ak_db:
                    ak_db.is_active = False
                    ak_db.revoked_at = ak.revoked_at
                    session.commit()
            except Exception as e:
                logger.warning("MCPKey revoke PG 持久化失败: %s", e)
            finally:
                if session:
                    session.close()
        logger.info("MCP 密钥已撤销: key_id=%s", key_id)
        return True

    def list_keys(self) -> list[dict]:
        """列出所有密钥元数据。"""
        return [
            {
                "key_id": ak.key_id,
                "name": ak.name,
                "scopes": ak.scopes,
                "status": ak.status,
                "created_at": ak.created_at.isoformat(),
                "revoked_at": ak.revoked_at.isoformat() if ak.revoked_at else None,
            }
            for ak in self._keys.values()
        ]
