"""reqradar-kernel — 最小共享内核（类型 / 枚举 / 异常 / ORM / 配置基类）。"""

from __future__ import annotations

__version__ = "2.0.0-alpha"

# 共享类型
# 配置基类
from reqradar.kernel.config_base import (
    ConfigMatrixBase,
    ConfigResolutionChain,
    ScopeDomainConfig,
)

# 数据库基类
from reqradar.kernel.database import Base, create_engine, create_session_factory

# 嵌入函数
from reqradar.kernel.embedding import ReqRadarEmbeddingFunction

# 全局枚举
from reqradar.kernel.enums import (
    ChangeStatus,
    CheckpointType,
    DimensionStatus,
    EventLevel,
    EventType,
    EvidenceStatus,
    EvidenceType,
    FreshnessStatus,
    KnowledgeNodeType,
    RelationType,
    ReleaseStatus,
    RiskLevel,
    SessionStatus,
    TaskStatus,
)

# 异常层次
from reqradar.kernel.exceptions import (
    CheckpointException,
    ConfigException,
    ContextBudgetExceededException,
    FatalError,
    GitException,
    IndexException,
    LLMException,
    LoaderException,
    ParseException,
    ReportException,
    ReqRadarException,
    SessionException,
    ToolExecutionError,
    VectorStoreException,
    VisionNotConfiguredError,
)
from reqradar.kernel.types import (
    ContextItem,
    ContextKind,
    Domain,
    Scope,
    ScoredContextItem,
    TokenBudget,
)

__all__ = [
    # 版本
    "__version__",
    # 类型
    "ContextItem",
    "ContextKind",
    "Domain",
    "ScoredContextItem",
    "Scope",
    "TokenBudget",
    # 枚举
    "ChangeStatus",
    "CheckpointType",
    "DimensionStatus",
    "EvidenceStatus",
    "EvidenceType",
    "EventLevel",
    "EventType",
    "FreshnessStatus",
    "KnowledgeNodeType",
    "ReleaseStatus",
    "RelationType",
    "RiskLevel",
    "SessionStatus",
    "TaskStatus",
    # 异常
    "CheckpointException",
    "ConfigException",
    "ContextBudgetExceededException",
    "FatalError",
    "GitException",
    "IndexException",
    "LLMException",
    "LoaderException",
    "ParseException",
    "ReportException",
    "ReqRadarException",
    "SessionException",
    "ToolExecutionError",
    "VectorStoreException",
    "VisionNotConfiguredError",
    # 数据库
    "Base",
    "create_engine",
    "create_session_factory",
    # 嵌入函数
    "ReqRadarEmbeddingFunction",
    # 配置
    "ConfigMatrixBase",
    "ConfigResolutionChain",
    "ScopeDomainConfig",
]
