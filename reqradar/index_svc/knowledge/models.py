"""L3 知识基础模型 — ConfidenceMetadata 与 L3KnowledgeBase。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from reqradar.kernel.enums import FreshnessStatus, KnowledgeNodeType

# 向后兼容别名
KnowledgeType = KnowledgeNodeType


@dataclass
class ConfidenceMetadata:
    """置信度元数据 — 追踪知识的验证次数与可信度。"""

    confidence_score: float = 0.5
    verification_count: int = 0
    human_verified: bool = False
    last_verified_at: datetime | None = None
    source_session_count: int = 0


@dataclass
class L3KnowledgeBase:
    """L3 知识基类 — 7 种知识类型共用的基础数据结构。"""

    id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    knowledge_type: KnowledgeNodeType = KnowledgeNodeType.GLOSSARY
    freshness: FreshnessStatus = FreshnessStatus.ACTIVE
    confidence: ConfidenceMetadata = field(default_factory=ConfidenceMetadata)
    source_session_ids: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
