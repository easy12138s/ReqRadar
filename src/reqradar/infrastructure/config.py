"""配置管理 - Pydantic 模型 + YAML 解析"""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


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


class GitConfig(BaseModel):
    lookback_months: int = Field(default=6)


class OutputConfig(BaseModel):
    report_template: str = Field(default="default")
    format: str = Field(default="markdown")


class LogConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="console")


class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    loader: LoaderConfig = Field(default_factory=LoaderConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    log: LogConfig = Field(default_factory=LogConfig)


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
    """加载配置文件"""
    if config_path is None:
        config_path = Path.cwd() / ".reqradar.yaml"

    if not config_path.exists():
        return Config()

    with open(config_path) as f:
        raw_config = yaml.safe_load(f) or {}

    resolved = _resolve_dict_env_vars(raw_config)
    return Config(**resolved)
