from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from reqradar.kernel.types import ContextKind

logger = logging.getLogger("reqradar.cognitive_rt.cognition.context_sources")


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

    def __init__(self) -> None:
        self._service_url = ""
        self._internal_api_key = ""

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
        if not self._service_url:
            logger.warning("ProjectMemorySource: service_url 未配置")
            return []
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "%s/internal/v2/knowledge/query" % self._service_url,
                    params={
                        "project_id": project_id,
                        "knowledge_types": "glossary,module_profile,architecture_constraint",
                    },
                    headers={"X-Internal-API-Key": self._internal_api_key},
                )
                if resp.status_code != 200:
                    logger.warning("ProjectMemorySource: HTTP %d", resp.status_code)
                    return []
                data = resp.json()
                items = []
                for ktype, entries in data.items():
                    if ktype == "project_id" or not isinstance(entries, list):
                        continue
                    for entry in entries:
                        items.append(
                            {
                                "type": ktype,
                                "content": entry.get("content", ""),
                                "topic": entry.get("topic", ""),
                            }
                        )
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "ProjectMemorySource: collected %d items, duration_ms=%d",
                    len(items),
                    duration_ms,
                )
                return items
        except Exception as e:
            logger.warning("ProjectMemorySource 收集失败: %s", e)
            return []


class UserMemorySource:
    """用户级记忆上下文适配器 — 提供用户个人偏好、历史决策等用户记忆。"""

    def __init__(self) -> None:
        self._service_url = ""
        self._internal_api_key = ""

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
        if not self._service_url:
            logger.warning("UserMemorySource: service_url 未配置")
            return []
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "%s/internal/v2/knowledge/query" % self._service_url,
                    params={"project_id": project_id, "knowledge_types": "historical_decision"},
                    headers={"X-Internal-API-Key": self._internal_api_key},
                )
                if resp.status_code != 200:
                    logger.warning("UserMemorySource: HTTP %d", resp.status_code)
                    return []
                data = resp.json()
                items = []
                for ktype, entries in data.items():
                    if ktype == "project_id" or not isinstance(entries, list):
                        continue
                    for entry in entries:
                        items.append(
                            {
                                "type": ktype,
                                "content": entry.get("content", ""),
                                "topic": entry.get("topic", ""),
                            }
                        )
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "UserMemorySource: collected %d items, duration_ms=%d", len(items), duration_ms
                )
                return items
        except Exception as e:
            logger.warning("UserMemorySource 收集失败: %s", e)
            return []


class CodeGraphSource:
    """代码图谱上下文适配器 — 提供源代码结构、调用关系等代码图谱信息。"""

    def __init__(self) -> None:
        self._service_url = ""
        self._internal_api_key = ""

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
        if not self._service_url:
            logger.warning("CodeGraphSource: service_url 未配置")
            return []
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "%s/internal/v2/search/vector" % self._service_url,
                    json={"project_id": project_id, "query": query, "top_k": 10},
                    headers={"X-Internal-API-Key": self._internal_api_key},
                )
                if resp.status_code != 200:
                    logger.warning("CodeGraphSource: HTTP %d", resp.status_code)
                    return []
                data = resp.json()
                items = []
                for entry in data if isinstance(data, list) else data.get("results", []):
                    items.append(
                        {
                            "content": entry.get("content", ""),
                            "source": entry.get("source", ""),
                            "score": entry.get("score", 0.0),
                        }
                    )
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "CodeGraphSource: collected %d items, duration_ms=%d", len(items), duration_ms
                )
                return items
        except Exception as e:
            logger.warning("CodeGraphSource 收集失败: %s", e)
            return []


class VectorResultSource:
    """向量检索上下文适配器 — 提供需求文档、设计文档等向量相似度检索结果。"""

    def __init__(self) -> None:
        self._service_url = ""
        self._internal_api_key = ""

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
        if not self._service_url:
            logger.warning("VectorResultSource: service_url 未配置")
            return []
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "%s/internal/v2/search/vector" % self._service_url,
                    json={"project_id": project_id, "query": query, "top_k": 10},
                    headers={"X-Internal-API-Key": self._internal_api_key},
                )
                if resp.status_code != 200:
                    logger.warning("VectorResultSource: HTTP %d", resp.status_code)
                    return []
                data = resp.json()
                items = []
                for entry in data if isinstance(data, list) else data.get("results", []):
                    items.append(
                        {
                            "content": entry.get("content", ""),
                            "source": entry.get("source", ""),
                            "score": entry.get("score", 0.0),
                        }
                    )
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "VectorResultSource: collected %d items, duration_ms=%d",
                    len(items),
                    duration_ms,
                )
                return items
        except Exception as e:
            logger.warning("VectorResultSource 收集失败: %s", e)
            return []


class GitHistorySource:
    """Git 历史上下文适配器 — 提供提交记录、变更历史等 Git 仓库信息。"""

    def __init__(self) -> None:
        self._service_url = ""
        self._internal_api_key = ""

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
        if not self._service_url:
            logger.warning("GitHistorySource: service_url 未配置")
            return []
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "%s/internal/v2/knowledge/query" % self._service_url,
                    params={"project_id": project_id, "knowledge_types": "pattern"},
                    headers={"X-Internal-API-Key": self._internal_api_key},
                )
                if resp.status_code != 200:
                    logger.warning("GitHistorySource: HTTP %d", resp.status_code)
                    return []
                data = resp.json()
                items = []
                for ktype, entries in data.items():
                    if ktype == "project_id" or not isinstance(entries, list):
                        continue
                    for entry in entries:
                        items.append(
                            {
                                "type": ktype,
                                "content": entry.get("content", ""),
                                "topic": entry.get("topic", ""),
                            }
                        )
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "GitHistorySource: collected %d items, duration_ms=%d", len(items), duration_ms
                )
                return items
        except Exception as e:
            logger.warning("GitHistorySource 收集失败: %s", e)
            return []
