from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import uuid4

from reqradar.kernel.types import ContextKind

logger = logging.getLogger(__name__)


class ContextItem:
    """上下文条目 — Pipeline 内部数据单元"""

    def __init__(
        self,
        content: str,
        context_kind: ContextKind,
        source_name: str,
        metadata: dict | None = None,
        token_count: int = 0,
        timestamp: datetime | None = None,
        user_marked: bool = False,
        l3_confidence: float | None = None,
    ) -> None:
        self.item_id = f"ctx-{uuid4().hex[:12]}"
        self.content = content
        self.context_kind = context_kind
        self.source_name = source_name
        self.metadata = metadata or {}
        self.token_count = token_count
        self.timestamp = timestamp or datetime.now(UTC)
        self.user_marked = user_marked
        self.l3_confidence = l3_confidence
        self.content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]


class ProjectMemorySource:
    """项目级记忆上下文适配器 — 提供术语表、模块画像、架构约束等项目记忆。"""

    def supported_kind(self) -> ContextKind:
        return ContextKind.MEMORY

    def is_available(self) -> bool:
        return True

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # TODO: P1 stub — 接入 V1 项目记忆数据源（术语表、模块画像、架构约束）
        logger.debug(
            "ProjectMemorySource.collect called: session=%s, project=%s, query=%r, max=%s",
            session_id,
            project_id,
            query,
            max_items,
        )
        return []


class UserMemorySource:
    """用户级记忆上下文适配器 — 提供用户个人偏好、历史决策等用户记忆。"""

    def supported_kind(self) -> ContextKind:
        return ContextKind.MEMORY

    def is_available(self) -> bool:
        return True

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # TODO: P1 stub — 接入 V1 用户记忆数据源（偏好设置、历史决策记录）
        logger.debug(
            f"UserMemorySource.collect called: "
            f"session={session_id}, project={project_id}, query={query!r}, max={max_items}"
        )
        return []


class CodeGraphSource:
    """代码图谱上下文适配器 — 提供源代码结构、调用关系等代码图谱信息。"""

    def supported_kind(self) -> ContextKind:
        return ContextKind.SOURCE_CODE

    def is_available(self) -> bool:
        return True

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # TODO: P1 stub — 接入 V1 代码图谱数据源（AST 索引、调用链、模块依赖）
        logger.debug(
            "CodeGraphSource.collect called: session=%s, project=%s, query=%r, max=%s",
            session_id,
            project_id,
            query,
            max_items,
        )
        return []


class VectorResultSource:
    """向量检索上下文适配器 — 提供需求文档、设计文档等向量相似度检索结果。"""

    def supported_kind(self) -> ContextKind:
        return ContextKind.REQUIREMENT

    def is_available(self) -> bool:
        return True

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # TODO: P1 stub — 接入 V1 向量检索数据源（ChromaDB 需求/设计文档相似度搜索）
        logger.debug(
            f"VectorResultSource.collect called: "
            f"session={session_id}, project={project_id}, query={query!r}, max={max_items}"
        )
        return []


class GitHistorySource:
    """Git 历史上下文适配器 — 提供提交记录、变更历史等 Git 仓库信息。"""

    def supported_kind(self) -> ContextKind:
        return ContextKind.GIT_HISTORY

    def is_available(self) -> bool:
        return True

    async def collect(
        self,
        session_id: str,
        project_id: str,
        query: str,
        max_items: int = 50,
    ) -> list[ContextItem]:
        # TODO: P1 stub — 接入 V1 Git 历史数据源（提交日志、diff、分支信息）
        logger.debug(
            "GitHistorySource.collect called: session=%s, project=%s, query=%r, max=%s",
            session_id,
            project_id,
            query,
            max_items,
        )
        return []
