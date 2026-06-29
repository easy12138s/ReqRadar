"""L3Writer — 统一知识写入接口（append / update / deprecate / supersede）。"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from reqradar.index_svc.knowledge.governance import (
    ConfidenceCalculator,
    FreshnessManager,
    KnowledgeChangelog,
)
from reqradar.index_svc.knowledge.models import (
    FreshnessStatus,
    L3KnowledgeBase,
)
from reqradar.index_svc.knowledge.relations import RelationStore

logger = logging.getLogger(__name__)


class L3Writer:
    """L3 知识写入器 — 7 种知识类型共用的统一写入接口。

    写入语义矩阵（M-03 §7.4）：
    - append: 新增知识
    - update: 更新已有知识（字段级变更）
    - deprecate: 标记为废弃
    - supersede: 替代旧知识
    """

    def __init__(
        self,
        freshness_manager: FreshnessManager | None = None,
        confidence_calculator: ConfidenceCalculator | None = None,
        changelog: KnowledgeChangelog | None = None,
        db_session_factory: object | None = None,
        relation_store: RelationStore | None = None,
    ) -> None:
        self._store: dict[str, L3KnowledgeBase] = {}
        self._freshness = freshness_manager or FreshnessManager()
        self._confidence = confidence_calculator or ConfidenceCalculator()
        self._changelog = changelog or KnowledgeChangelog()
        self._db_session_factory = db_session_factory
        self._relation_store = relation_store or RelationStore()
        self._pending_tasks: set[asyncio.Task] = set()

    def append(self, knowledge: L3KnowledgeBase, session_id: str = "", links: list | None = None) -> L3KnowledgeBase:
        """新增知识条目。"""
        knowledge.confidence.confidence_score = self._confidence.calculate(knowledge)
        self._store[knowledge.id] = knowledge
        self._changelog.record(
            knowledge_id=knowledge.id,
            knowledge_type=knowledge.knowledge_type.value,
            action="create",
            session_id=session_id,
        )
        logger.info("知识新增: %s (%s)", knowledge.id, knowledge.knowledge_type.value)

        if self._db_session_factory:
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(self._persist_to_pg(knowledge))
                self._pending_tasks.add(task)
                task.add_done_callback(self._pending_tasks.discard)
            except RuntimeError:
                logger.debug("无运行事件循环，跳过 L3 知识 PG 持久化")

        if links:
            self._relation_store.add_batch(links)

        return knowledge

    def update(
        self,
        knowledge_id: str,
        updates: dict,
        session_id: str = "",
    ) -> L3KnowledgeBase | None:
        """更新已有知识（字段级变更追踪）。"""
        existing = self._store.get(knowledge_id)
        if existing is None:
            return None

        field_changes = []
        for key, new_value in updates.items():
            old_value = getattr(existing, key, None)
            if old_value != new_value:
                field_changes.append(
                    {
                        "field": key,
                        "old": str(old_value)[:200],
                        "new": str(new_value)[:200],
                    }
                )
                setattr(existing, key, new_value)

        existing.updated_at = datetime.now(UTC)
        existing.confidence = self._confidence.on_verification(existing, session_id)

        self._changelog.record(
            knowledge_id=knowledge_id,
            knowledge_type=existing.knowledge_type.value,
            action="update",
            field_changes=field_changes,
            session_id=session_id,
        )
        return existing

    def deprecate(self, knowledge_id: str, session_id: str = "") -> L3KnowledgeBase | None:
        """标记知识为废弃。"""
        existing = self._store.get(knowledge_id)
        if existing is None:
            return None

        existing.freshness = FreshnessStatus.DEPRECATED
        existing.updated_at = datetime.now(UTC)
        self._changelog.record(
            knowledge_id=knowledge_id,
            knowledge_type=existing.knowledge_type.value,
            action="deprecate",
            session_id=session_id,
        )
        return existing

    def supersede(
        self, old_id: str, new_knowledge: L3KnowledgeBase, session_id: str = ""
    ) -> L3KnowledgeBase | None:
        """用新知识替代旧知识。"""
        old = self._store.get(old_id)
        if old is None:
            return self.append(new_knowledge, session_id)

        old.freshness = FreshnessStatus.SUPERSEDED
        old.superseded_by = new_knowledge.id
        old.updated_at = datetime.now(UTC)

        new_knowledge = self.append(new_knowledge, session_id)
        self._changelog.record(
            knowledge_id=old_id,
            knowledge_type=old.knowledge_type.value,
            action="supersede",
            field_changes=[{"field": "superseded_by", "old": "None", "new": new_knowledge.id}],
            session_id=session_id,
        )
        return new_knowledge

    def get(self, knowledge_id: str) -> L3KnowledgeBase | None:
        """获取知识条目。"""
        return self._store.get(knowledge_id)

    def query_active(self, project_id: str) -> list[L3KnowledgeBase]:
        """查询项目下所有 active 知识。"""
        return [
            k
            for k in self._store.values()
            if k.project_id == project_id and k.freshness == FreshnessStatus.ACTIVE
        ]

    def get_all(self) -> list[L3KnowledgeBase]:
        """获取所有知识。"""
        return list(self._store.values())

    async def _persist_to_pg(self, knowledge: L3KnowledgeBase) -> None:
        """将 L3 知识持久化到 PostgreSQL。"""
        try:
            from reqradar.kernel.models import L3Knowledge as L3KnowledgeModel

            async with self._db_session_factory() as db_session:
                db_session.add(
                    L3KnowledgeModel(
                        id=knowledge.id,
                        project_id=knowledge.project_id,
                        knowledge_type=(
                            knowledge.knowledge_type.value
                            if hasattr(knowledge.knowledge_type, "value")
                            else str(knowledge.knowledge_type)
                        ),
                        freshness=(
                            knowledge.freshness.value
                            if hasattr(knowledge.freshness, "value")
                            else str(knowledge.freshness)
                        ),
                        confidence_score=knowledge.confidence.confidence_score,
                        confidence_data={
                            "verification_count": knowledge.confidence.verification_count,
                            "human_verified": knowledge.confidence.human_verified,
                            "last_verified_at": (
                                knowledge.confidence.last_verified_at.isoformat()
                                if knowledge.confidence.last_verified_at
                                else None
                            ),
                            "source_session_count": knowledge.confidence.source_session_count,
                        },
                        source_session_ids=knowledge.source_session_ids,
                        superseded_by=knowledge.superseded_by,
                    )
                )
                await db_session.commit()
        except Exception as e:
            logger.warning("L3 知识 PG 持久化失败: %s", e)
