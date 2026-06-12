"""配置管理 — 从环境变量读取所有配置。"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger("reqradar.infrastructure.config")


def _env(key: str, default: str = "") -> str:
    """读取环境变量，先尝试 REQRADAR_ 前缀，再尝试无前缀。"""
    prefixed = "REQRADAR_" + key
    value = os.environ.get(prefixed)
    if value is not None:
        return value
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    """读取整数环境变量。"""
    return int(_env(key, str(default)))


@dataclass(frozen=True)
class LLMConfig:
    """LLM 配置。"""

    api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    model: str = field(default_factory=lambda: _env("LLM_MODEL", "gpt-4o-mini"))
    base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "https://api.openai.com/v1"))
    timeout: float = 120.0
    max_retries: int = 3


@dataclass(frozen=True)
class DatabaseConfig:
    """数据库配置。"""

    url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "sqlite+aiosqlite:///./reqradar_dev.db")
    )


@dataclass(frozen=True)
class RedisConfig:
    """Redis 配置。"""

    url: str = field(default_factory=lambda: _env("REDIS_URL", ""))


@dataclass(frozen=True)
class AuthConfig:
    """认证配置。"""

    jwt_secret: str = field(default_factory=lambda: _env("JWT_SECRET", ""))
    internal_api_key: str = field(default_factory=lambda: _env("INTERNAL_API_KEY", ""))


@dataclass(frozen=True)
class ServiceURLs:
    """服务地址配置。"""

    auth: str = field(default_factory=lambda: _env("AUTH_SERVICE_URL", "http://localhost:8001"))
    cognitive_rt: str = field(
        default_factory=lambda: _env("COGNITIVE_RT_URL", "http://localhost:8002")
    )
    index: str = field(default_factory=lambda: _env("INDEX_SERVICE_URL", "http://localhost:8003"))
    output: str = field(default_factory=lambda: _env("OUTPUT_SERVICE_URL", "http://localhost:8004"))
    integration: str = field(
        default_factory=lambda: _env("INTEGRATION_SERVICE_URL", "http://localhost:8005")
    )


@dataclass(frozen=True)
class MCPConfig:
    """MCP 配置。"""

    host: str = field(default_factory=lambda: _env("MCP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("MCP_PORT", 9000))
    path: str = field(default_factory=lambda: _env("MCP_PATH", "/mcp"))


@dataclass(frozen=True)
class EmbeddingConfig:
    """嵌入配置（独立于 LLM，解耦供应商）。"""

    provider: str = field(default_factory=lambda: _env("EMBEDDING__PROVIDER", "openai"))
    model: str = field(
        default_factory=lambda: _env("EMBEDDING__MODEL", "text-embedding-3-small")
    )
    api_key: str = field(default_factory=lambda: _env("EMBEDDING__API_KEY", ""))
    api_base: str = field(
        default_factory=lambda: _env("EMBEDDING__API_BASE", "https://api.openai.com/v1")
    )
    dimensions: int = field(default_factory=lambda: _env_int("EMBEDDING__DIMENSIONS", 384))


@dataclass(frozen=True)
class AppConfig:
    """应用全局配置。"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    services: ServiceURLs = field(default_factory=ServiceURLs)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))


def load_config() -> AppConfig:
    """加载全局配置。"""
    config = AppConfig()
    logger.info("配置加载完成: llm_model=%s, db_url=%s", config.llm.model, config.db.url[:30])
    return config
