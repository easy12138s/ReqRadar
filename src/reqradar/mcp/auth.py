import logging
from dataclasses import dataclass

from reqradar.web.models import MCPAccessKey
from reqradar.web.services.mcp_auth_service import verify_key

logger = logging.getLogger("reqradar.mcp.auth")


@dataclass
class MCPAuthResult:
    access_key: MCPAccessKey
    key_id: int
    user_id: int
    scopes: list[str]


def parse_bearer_token(auth_header: str | None) -> str | None:
    """Extract Bearer token from Authorization header. Returns raw key or None."""
    if not auth_header:
        return None
    parts = auth_header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
        if token.startswith("rr_mcp_"):
            return token
    return None


async def authenticate_mcp_request(auth_header: str | None, db) -> MCPAuthResult | None:
    """Verify MCP Bearer token against DB. Returns MCPAuthResult or None."""
    raw_key = parse_bearer_token(auth_header)
    if raw_key is None:
        return None
    access_key = await verify_key(db, raw_key)
    if access_key is None:
        return None
    return MCPAuthResult(
        access_key=access_key,
        key_id=access_key.id,
        user_id=access_key.user_id,
        scopes=access_key.scopes,
    )
