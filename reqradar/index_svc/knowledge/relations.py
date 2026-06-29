"""knowledge_relations — 统一关系存储 + Relation Contract 接口。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from reqradar.kernel.enums import RelationType

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeRelation:
    """知识关系记录。"""

    id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    source_layer: str = ""
    source_type: str = ""
    source_id: str = ""
    target_layer: str = ""
    relation_type: RelationType = RelationType.DEPENDS_ON
    target_type: str = ""
    target_id: str = ""
    confidence: float = 0.5
    evidence_ref: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RelationStore:
    """关系存储 — 基于内存的关系图谱（P5 阶段，后续迁移到 PG）。"""

    def __init__(self) -> None:
        self._relations: list[KnowledgeRelation] = []
        self._db_session_factory = None
        self._http_base_url = ""
        self._http_api_key = ""

    def set_session_factory(self, factory):
        self._db_session_factory = factory

    def set_http_client(self, base_url: str, api_key: str):
        self._http_base_url = base_url
        self._http_api_key = api_key

    def add(self, relation: KnowledgeRelation) -> KnowledgeRelation:
        """添加关系。"""
        self._relations.append(relation)
        return relation

    def query(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: RelationType | None = None,
    ) -> list[KnowledgeRelation]:
        """查询关系。"""
        results = self._relations
        if source_id:
            results = [r for r in results if r.source_id == source_id]
        if target_id:
            results = [r for r in results if r.target_id == target_id]
        if relation_type:
            results = [r for r in results if r.relation_type == relation_type]
        return results

    def get_related(self, knowledge_id: str) -> list[KnowledgeRelation]:
        """获取与指定知识相关的所有关系。"""
        return [
            r for r in self._relations if r.source_id == knowledge_id or r.target_id == knowledge_id
        ]

    def remove(self, relation_id: str) -> bool:
        """删除关系。"""
        for i, r in enumerate(self._relations):
            if r.id == relation_id:
                self._relations.pop(i)
                return True
        return False

    def _persist(self, relation: KnowledgeRelation) -> None:
        if not self._db_session_factory:
            return
        try:
            from reqradar.kernel.models import EntityLink

            session = self._db_session_factory()
            session.add(
                EntityLink(
                    id=relation.id,
                    project_id=relation.project_id,
                    source_layer=relation.source_layer,
                    source_type=relation.source_type,
                    source_id=relation.source_id,
                    target_layer=relation.target_layer,
                    target_type=relation.target_type,
                    target_id=relation.target_id,
                    relation_type=(
                        relation.relation_type.value
                        if hasattr(relation.relation_type, "value")
                        else str(relation.relation_type)
                    ),
                    confidence=relation.confidence,
                    evidence=relation.evidence_ref,
                )
            )
            session.commit()
            session.close()
        except Exception as e:
            logger.warning("关系持久化失败: %s", e)

    def add_batch(self, relations: list[KnowledgeRelation]) -> None:
        for r in relations:
            self.add(r)
            self._persist(r)
