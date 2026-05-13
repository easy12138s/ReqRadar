import logging
import secrets

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import MCPConfig
from reqradar.web.models import MCPAccessKey, utc_now

logger = logging.getLogger("reqradar.mcp_auth")

KEY_PREFIX_LEN = 12


def _hash_key(raw_key: str) -> str:
    return bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_key(raw_key: str, key_hash: str) -> bool:
    return bcrypt.checkpw(raw_key.encode("utf-8"), key_hash.encode("utf-8"))


def build_mcp_public_url(config: MCPConfig) -> str:
    if config.public_url:
        url = config.public_url.rstrip("/")
        if not url.endswith(config.path):
            url = f"{url}{config.path}"
        return url
    host = "localhost" if config.host == "0.0.0.0" else config.host
    return f"http://{host}:{config.port}{config.path}"


async def generate_key(
    db: AsyncSession,
    user_id: int,
    name: str,
    scopes: list[str],
    config: MCPConfig,
) -> dict:
    raw_key = f"rr_mcp_{secrets.token_urlsafe(32)}"
    key_prefix = raw_key[:KEY_PREFIX_LEN]
    key_hash = _hash_key(raw_key)

    access_key = MCPAccessKey(
        user_id=user_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=name,
        scopes=scopes,
    )
    db.add(access_key)
    await db.commit()
    await db.refresh(access_key)

    logger.info(
        "MCP access key created: id=%d prefix=%s user=%d", access_key.id, key_prefix, user_id
    )

    return {
        "mcpServers": {
            "reqradar": {
                "url": build_mcp_public_url(config),
                "headers": {"Authorization": f"Bearer {raw_key}"},
            }
        }
    }


async def verify_key(db: AsyncSession, raw_key: str) -> MCPAccessKey | None:
    key_prefix = raw_key[:KEY_PREFIX_LEN]

    stmt = select(MCPAccessKey).where(
        MCPAccessKey.key_prefix == key_prefix,
        MCPAccessKey.is_active.is_(True),
    )
    result = await db.execute(stmt)
    candidates = result.scalars().all()

    for candidate in candidates:
        if _verify_key(raw_key, candidate.key_hash):
            candidate.last_used_at = utc_now()
            await db.commit()
            await db.refresh(candidate)
            return candidate

    return None


async def revoke_key(db: AsyncSession, key_id: int, user_id: int) -> MCPAccessKey | None:
    stmt = select(MCPAccessKey).where(MCPAccessKey.id == key_id, MCPAccessKey.user_id == user_id)
    result = await db.execute(stmt)
    access_key = result.scalar_one_or_none()

    if access_key is None:
        return None

    access_key.is_active = False
    access_key.revoked_at = utc_now()
    await db.commit()
    await db.refresh(access_key)

    logger.info("MCP access key revoked: id=%d user=%d", key_id, user_id)

    return access_key


async def re_export_key(
    db: AsyncSession,
    key_id: int,
    user_id: int,
    config: MCPConfig,
) -> dict | None:
    stmt = select(MCPAccessKey).where(MCPAccessKey.id == key_id, MCPAccessKey.user_id == user_id)
    result = await db.execute(stmt)
    access_key = result.scalar_one_or_none()

    if access_key is None:
        return None

    return {
        "mcp_config": build_mcp_public_url(config),
        "note": "Raw key was only shown once at creation time",
    }


async def list_keys(db: AsyncSession, user_id: int) -> list[MCPAccessKey]:
    stmt = (
        select(MCPAccessKey)
        .where(MCPAccessKey.user_id == user_id)
        .order_by(MCPAccessKey.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
