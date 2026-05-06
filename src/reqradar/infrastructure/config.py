"""配置管理 - Pydantic 模型 + YAML 解析"""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class LLMConfig(BaseModel):
    provider: str = Field(default="openai", description="LLM provider: openai or ollama")
    model: str = Field(default="gpt-4o-mini", description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key (or env var reference)")
    base_url: Optional[str] = Field(default=None, description="OpenAI-compatible API base URL")
    timeout: int = Field(default=60, description="Request timeout in seconds")
    max_retries: int = Field(default=2, description="Max retry attempts")
    host: Optional[str] = Field(default=None, description="Ollama host")

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_env_var(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v


class VisionConfig(BaseModel):
    provider: str = Field(default="openai", description="Vision LLM provider")
    model: str = Field(default="gpt-4o", description="Vision model name")
    api_key: Optional[str] = Field(default=None, description="API key (or env var reference)")
    base_url: Optional[str] = Field(default=None, description="OpenAI-compatible API base URL")
    timeout: int = Field(default=120, description="Timeout for vision requests")
    max_retries: int = Field(default=2, description="Max retry attempts")

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_env_var(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v


class MemoryConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable project memory")
    storage_path: str = Field(default=".reqradar/memory", description="Memory storage directory")
    project_storage_path: str = Field(
        default=".reqradar/memories", description="Project memory storage path"
    )
    user_storage_path: str = Field(
        default=".reqradar/user_memories", description="User memory storage path"
    )


class MemoryEvolutionConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable post-analysis memory self-evolution")


class LoaderConfig(BaseModel):
    chunk_size: int = Field(default=300, description="Default chunk size for text splitting")
    chunk_overlap: int = Field(default=50, description="Default overlap for text splitting")
    pdf_enabled: bool = Field(default=True, description="Enable PDF loader")
    docx_enabled: bool = Field(default=True, description="Enable DOCX loader")
    image_enabled: bool = Field(default=True, description="Enable image loader")
    chat_enabled: bool = Field(default=True, description="Enable chat loader")


class IndexConfig(BaseModel):
    embedding_model: str = Field(default="BAAI/bge-large-zh")
    chunk_size: int = Field(default=300)
    chunk_overlap: int = Field(default=50)
    storage_path: str = Field(default=".reqradar/index")


class AnalysisConfig(BaseModel):
    max_similar_reqs: int = Field(default=5)
    max_code_files: int = Field(default=10)
    contributors_lookback_months: int = Field(default=6)
    tool_use_enabled: bool = Field(default=True, description="启用LLM工具调用循环")


class AgentConfig(BaseModel):
    max_steps: int = Field(default=15, description="Max agent steps for standard depth")
    max_steps_quick: int = Field(default=10, description="Max agent steps for quick depth")
    max_steps_deep: int = Field(default=25, description="Max agent steps for deep depth")
    version_limit: int = Field(default=10, description="Max report versions per task")
    sensitive_file_patterns: list[str] = Field(
        default_factory=lambda: [
            ".env",
            ".env.*",
            "*.key",
            "*.pem",
            "*.crt",
            "secrets/",
            "credentials/",
            ".aws/",
            ".ssh/",
        ],
        description="Sensitive file patterns to block agent access",
    )


class ReportingConfig(BaseModel):
    default_template_id: int = Field(default=1, description="Default report template ID")


class GitConfig(BaseModel):
    lookback_months: int = Field(default=6)


class OutputConfig(BaseModel):
    report_template: str = Field(default="default")
    format: str = Field(default="markdown")


class LogConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="console")


class WebConfig(BaseModel):
    host: str = Field(default="0.0.0.0", description="Web server bind host")
    port: int = Field(default=8000, description="Web server bind port")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./reqradar.db", description="Async database URL"
    )
    secret_key: str = Field(default="change-me-in-production", description="JWT secret key")
    access_token_expire_minutes: int = Field(
        default=1440, description="JWT access token expiry in minutes"
    )
    max_concurrent_analyses: int = Field(default=2, description="Maximum concurrent analysis tasks")
    max_upload_size: int = Field(default=50, description="Maximum file upload size in MB")
    cors_origins: Optional[str] = Field(
        default=None, description="CORS allowed origins (JSON array string or empty for all)"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    static_dir: Optional[str] = Field(default=None, description="Static files directory path")
    auto_create_tables: bool = Field(
        default=False,
        description="Auto-create DB tables on startup (dev only, prefer Alembic for production)",
    )
    allowed_upload_extensions: str = Field(
        default=".txt,.md,.pdf,.docx,.xlsx,.csv,.json,.yaml,.yml,.html,.png,.jpg,.jpeg,.gif,.bmp",
        description="Comma-separated list of allowed file upload extensions",
    )
    db_pool_size: int = Field(default=5, description="Database connection pool size")
    db_pool_max_overflow: int = Field(
        default=10, description="Max overflow connections beyond pool_size"
    )
    data_root: str = Field(
        default="~/.reqradar/data",
        description="Root directory for project file storage (supports ~ expansion)",
    )

    @field_validator("secret_key", mode="before")
    @classmethod
    def resolve_env_var(cls, v: Optional[str]) -> Optional[str]:
        if v and isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v


class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    memory_evolution: MemoryEvolutionConfig = Field(default_factory=MemoryEvolutionConfig)
    loader: LoaderConfig = Field(default_factory=LoaderConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    web: WebConfig = Field(default_factory=WebConfig)

    @model_validator(mode="after")
    def _validate_critical_settings(self) -> "Config":
        if (
            self.web.secret_key == "change-me-in-production"
            and not self.web.debug
            and not os.getenv("REQRADAR_TESTING")
        ):
            raise ValueError(
                "web.secret_key must be changed from default in production mode. "
                "Set REQRADAR_SECRET_KEY env var or web.secret_key in .reqradar.yaml"
            )
        return self


def _resolve_env_vars(value: str) -> str:
    pattern = r"\$\{([^}]+)\}"
    matches = re.findall(pattern, value)
    for match in matches:
        value = value.replace(f"${{{match}}}", os.getenv(match, ""))
    return value


def _resolve_dict_env_vars(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = _resolve_env_vars(v)
        elif isinstance(v, dict):
            result[k] = _resolve_dict_env_vars(v)
        elif isinstance(v, list):
            result[k] = [_resolve_env_vars(item) if isinstance(item, str) else item for item in v]
        else:
            result[k] = v
    return result


def load_config(config_path: Optional[Path] = None) -> Config:
    """加载配置文件，支持回退路径"""
    if config_path is None:
        config_path = Path.cwd() / ".reqradar.yaml"
        if not config_path.exists():
            fallback = Path.cwd() / ".reqradar" / "config.yaml"
            if fallback.exists():
                config_path = fallback

    if not config_path.exists():
        return Config()

    with open(config_path) as f:
        raw_config = yaml.safe_load(f) or {}

    resolved = _resolve_dict_env_vars(raw_config)
    return Config(**resolved)
