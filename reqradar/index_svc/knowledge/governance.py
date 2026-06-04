"""L3 知识治理框架 — 新鲜度管理、置信度计算、变更日志。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from reqradar.index_svc.knowledge.models import (
    FreshnessStatus,
    L3KnowledgeBase,
)

logger = logging.getLogger(__name__)

# 新鲜度阈值（天）
STALE_THRESHOLD_DAYS = 90
HISTORICAL_THRESHOLD_DAYS = 180


class FreshnessManager:
    """知识新鲜度管理器。"""

    def __init__(self, stale_days: int = STALE_THRESHOLD_DAYS) -> None:
        self._stale_days = stale_days

    def check_staleness(self, knowledge: L3KnowledgeBase) -> FreshnessStatus:
        """检查知识是否过期。"""
        if knowledge.freshness in (
            FreshnessStatus.DEPRECATED,
            FreshnessStatus.SUPERSEDED,
        ):
            return knowledge.freshness

        if knowledge.confidence.last_verified_at is None:
            # 从未被验证，用创建时间判断
            age = datetime.now(UTC) - knowledge.created_at
        else:
            age = datetime.now(UTC) - knowledge.confidence.last_verified_at

        if age > timedelta(days=self._stale_days):
            return FreshnessStatus.STALE

        return knowledge.freshness

    def update_freshness(self, knowledge: L3KnowledgeBase) -> L3KnowledgeBase:
        """更新知识新鲜度状态。"""
        new_status = self.check_staleness(knowledge)
        if new_status != knowledge.freshness:
            logger.info(f"知识 {knowledge.id} 新鲜度变更: {knowledge.freshness} -> {new_status}")
            knowledge.freshness = new_status
            knowledge.updated_at = datetime.now(UTC)
        return knowledge

    def mark_conflicted(self, knowledge: L3KnowledgeBase) -> L3KnowledgeBase:
        """标记知识为冲突状态。"""
        knowledge.freshness = FreshnessStatus.CONFLICTED
        knowledge.updated_at = datetime.now(UTC)
        return knowledge


class ConfidenceCalculator:
    """知识置信度计算器。"""

    def calculate(self, knowledge: L3KnowledgeBase) -> float:
        """计算综合置信度评分。

        公式: base_score + verification_bonus + human_bonus - staleness_penalty
        """
        base = knowledge.confidence.confidence_score
        verification_bonus = min(knowledge.confidence.verification_count * 0.05, 0.3)
        human_bonus = 0.2 if knowledge.confidence.human_verified else 0.0

        staleness_penalty = 0.0
        if knowledge.confidence.last_verified_at:
            days_since = (datetime.now(UTC) - knowledge.confidence.last_verified_at).days
            staleness_penalty = min(days_since / 365.0, 0.3)

        score = base + verification_bonus + human_bonus - staleness_penalty
        return max(0.0, min(1.0, score))

    def on_verification(self, knowledge: L3KnowledgeBase, session_id: str) -> L3KnowledgeBase:
        """记录一次验证。"""
        knowledge.confidence.verification_count += 1
        knowledge.confidence.last_verified_at = datetime.now(UTC)
        if session_id not in knowledge.source_session_ids:
            knowledge.source_session_ids.append(session_id)
            knowledge.confidence.source_session_count = len(knowledge.source_session_ids)
        knowledge.confidence.confidence_score = self.calculate(knowledge)
        knowledge.updated_at = datetime.now(UTC)
        return knowledge

    def on_human_verify(self, knowledge: L3KnowledgeBase) -> L3KnowledgeBase:
        """记录人工确认。"""
        knowledge.confidence.human_verified = True
        knowledge.confidence.verification_count += 1
        knowledge.confidence.last_verified_at = datetime.now(UTC)
        knowledge.confidence.confidence_score = self.calculate(knowledge)
        knowledge.updated_at = datetime.now(UTC)
        return knowledge


@dataclass
class ChangelogEntry:
    """变更日志条目。"""

    id: str = field(default_factory=lambda: str(uuid4()))
    knowledge_id: str = ""
    knowledge_type: str = ""
    action: str = ""  # create / update / verify / deprecate / supersede
    field_changes: list[dict] = field(default_factory=list)
    session_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class KnowledgeChangelog:
    """知识变更日志 — append-only 记录所有知识变更。"""

    def __init__(self) -> None:
        self._entries: list[ChangelogEntry] = []

    def record(
        self,
        knowledge_id: str,
        knowledge_type: str,
        action: str,
        field_changes: list[dict] | None = None,
        session_id: str = "",
    ) -> ChangelogEntry:
        """记录一次变更。"""
        entry = ChangelogEntry(
            knowledge_id=knowledge_id,
            knowledge_type=knowledge_type,
            action=action,
            field_changes=field_changes or [],
            session_id=session_id,
        )
        self._entries.append(entry)
        return entry

    def get_history(self, knowledge_id: str) -> list[ChangelogEntry]:
        """获取某条知识的变更历史。"""
        return [e for e in self._entries if e.knowledge_id == knowledge_id]

    def get_recent(self, limit: int = 100) -> list[ChangelogEntry]:
        """获取最近的变更记录。"""
        return self._entries[-limit:]
