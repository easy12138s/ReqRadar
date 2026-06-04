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
    source_type: str = ""
    source_id: str = ""
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
