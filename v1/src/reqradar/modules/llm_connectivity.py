import time
import logging

logger = logging.getLogger("reqradar.llm_connectivity")

_cache: dict[str, tuple[bool, float]] = {}
CACHE_TTL_SECONDS = 300


def _make_key(provider: str, api_key: str, base_url: str) -> str:
    return f"{provider}::{api_key[:8]}::{base_url}"


def is_llm_reachable(provider: str, api_key: str, base_url: str) -> bool | None:
    key = _make_key(provider, api_key, base_url)
    entry = _cache.get(key)
    if entry is None:
        return None
    reachable, ts = entry
    if time.time() - ts > CACHE_TTL_SECONDS:
        del _cache[key]
        return None
    return reachable


def mark_llm_reachable(provider: str, api_key: str, base_url: str) -> None:
    key = _make_key(provider, api_key, base_url)
    _cache[key] = (True, time.time())
    logger.info("LLM connectivity marked as reachable for %s", key)


def mark_llm_unreachable(provider: str, api_key: str, base_url: str) -> None:
    key = _make_key(provider, api_key, base_url)
    _cache[key] = (False, time.time())
    logger.info("LLM connectivity marked as unreachable for %s", key)
