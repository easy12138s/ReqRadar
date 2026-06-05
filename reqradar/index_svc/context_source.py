"""L3ContextSource — Context Pipeline Collect 阶段的 L3 知识注入适配器。"""

from __future__ import annotations

import logging

from reqradar.index_svc.knowledge.governance import (
    FreshnessManager,
)
from reqradar.index_svc.knowledge.models import (
    L3KnowledgeBase,
)
from reqradar.kernel.enums import FreshnessStatus
from reqradar.kernel.types import ContextItem, ContextKind

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE = 0.6
_DEFAULT_MAX_ITEMS = 20


class L3ContextSource:
    """L3 持久化知识数据源 — 供 Context Pipeline Collect 阶段调用。

    过滤规则（R-02 §5.3）：
    - freshness = active
    - confidence_score >= 0.6
    - 按 confidence_score 降序排列
    """

    def __init__(
        self,
        knowledge_store: object | None = None,
        freshness_manager: FreshnessManager | None = None,
        min_confidence: float = _MIN_CONFIDENCE,
    ) -> None:
        self._store = knowledge_store
        self._freshness = freshness_manager or FreshnessManager()
        self._min_confidence = min_confidence

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        context_kind: ContextKind = ContextKind.MEMORY,
        max_items: int = _DEFAULT_MAX_ITEMS,
    ) -> list[ContextItem]:
        """从 L3 知识库收集上下文。

        Args:
            session_id: 当前 Session ID
            project_id: 项目 ID
            query: 当前推理步骤的查询意图
            context_kind: 上下文类型（默认 MEMORY）
            max_items: 最大返回条目数

        Returns:
            过滤后的 ContextItem 列表
        """
        if self._store is None:
            return []

        try:
            all_knowledge = self._store.query_active(project_id)
        except Exception as e:
            logger.warning("L3 知识查询失败: %s", e)
            return []

        qualified = []
        for k in all_knowledge:
            status = self._freshness.check_staleness(k)
            if status != FreshnessStatus.ACTIVE:
                continue

            if k.confidence.confidence_score < self._min_confidence:
                continue

            qualified.append(k)

        qualified.sort(key=lambda x: x.confidence.confidence_score, reverse=True)

        items = []
        for k in qualified[:max_items]:
            content = self._format_knowledge(k)
            items.append(
                ContextItem(
                    content=content,
                    kind=context_kind,
                    source_uri=f"l3://{k.knowledge_type.value}/{k.id}",
                    metadata={
                        "knowledge_id": k.id,
                        "knowledge_type": k.knowledge_type.value,
                        "confidence_score": k.confidence.confidence_score,
                        "freshness": k.freshness.value,
                        "retrieval_score": k.confidence.confidence_score,
                    },
                )
            )

        logger.info(
            "L3 知识收集: project=%s, qualified=%s, returned=%s",
            project_id,
            len(qualified),
            len(items),
        )
        return items

    def _format_knowledge(self, k: L3KnowledgeBase) -> str:
        """格式化知识为文本。"""
        lines = [f"[{k.knowledge_type.value}] {k.id}"]

        canonical_name = getattr(k, "canonical_name", "")
        definition = getattr(k, "definition", "")
        module_name = getattr(k, "module_name", "")
        responsibility = getattr(k, "responsibility", "")
        title = getattr(k, "title", "")
        constraint_type = getattr(k, "constraint_type", "")
        description = getattr(k, "description", "")
        risk_description = getattr(k, "risk_description", "")

        if canonical_name:
            lines.append(f"术语: {canonical_name}")
            if definition:
                lines.append(f"定义: {definition}")

        if module_name:
            lines.append(f"模块: {module_name}")
            if responsibility:
                lines.append(f"职责: {responsibility}")

        if title:
            lines.append(f"标题: {title}")

        if constraint_type:
            lines.append(f"约束类型: {constraint_type}")
            if description:
                lines.append(f"描述: {description}")

        if risk_description:
            lines.append(f"风险: {risk_description}")

        lines.append(f"置信度: {k.confidence.confidence_score:.2f}")
        lines.append(f"新鲜度: {k.freshness.value}")

        return "\n".join(lines)

    def supported_kind(self) -> ContextKind:
        """返回支持的 ContextKind。"""
        return ContextKind.MEMORY

    def is_available(self, project_id: str) -> bool:
        """检查是否可用。"""
        return self._store is not None
