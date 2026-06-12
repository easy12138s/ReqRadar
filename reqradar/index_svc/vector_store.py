"""向量存储 — PgVectorStore，直接查询 PostgreSQL embedding 列。

替代 ChromaDB，将嵌入向量存储在 PG 现有表的 embedding JSON 列中。
- PostgreSQL 环境：使用 pgvector 扩展的 HNSW 索引（embedding_vector 列）
- SQLite 环境：应用层余弦相似度计算
"""

from __future__ import annotations

import logging
import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger("reqradar.vector_store")


@dataclass
class Document:
    """向量存储文档。"""

    id: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    """搜索结果。"""

    id: str
    content: str
    metadata: dict
    distance: float


class VectorStore(ABC):
    """向量存储基类。"""

    @abstractmethod
    async def add_document(self, doc: Document) -> None:
        """添加单个文档。"""

    @abstractmethod
    async def add_documents(self, docs: list[Document]) -> list[str]:
        """批量添加文档，返回 ID 列表。"""

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """搜索相似文档。"""

    @abstractmethod
    async def persist(self) -> None:
        """持久化数据到磁盘（pgvector 无需额外操作）。"""


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算余弦相似度。"""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


_COLLECTION_TABLE_MAP = {
    "requirements": ("chunks", "id", "content", "embedding"),
    "code": ("code_modules", "id", "signature", "embedding"),
}


class PgVectorStore(VectorStore):
    """PostgreSQL 向量存储 — 直接查询现有表的 embedding JSON 列。

    在 PostgreSQL 上使用 pgvector 扩展的 HNSW 索引（embedding_vector 列），
    在 SQLite 上退化为应用层余弦相似度计算。
    """

    def __init__(
        self,
        db_session_factory,
        collection_name: str = "requirements",
        embedding_fn=None,
    ) -> None:
        self._db_session_factory = db_session_factory
        self._collection_name = collection_name
        self._embedding_fn = embedding_fn

        table_info = _COLLECTION_TABLE_MAP.get(collection_name)
        if table_info is None:
            raise ValueError(f"未知集合: {collection_name}，可选: {list(_COLLECTION_TABLE_MAP)}")
        self._table_name, self._id_col, self._content_col, self._embedding_col = table_info

    def _get_embedding(self, text: str) -> list[float]:
        """计算文本的嵌入向量。"""
        if self._embedding_fn is None:
            from reqradar.kernel.embedding import ReqRadarEmbeddingFunction

            self._embedding_fn = ReqRadarEmbeddingFunction()
        result = self._embedding_fn([text])
        return result[0] if result else []

    def _is_postgres(self):
        """检测数据库后端类型。"""
        try:

            # 无法直接获取 dialect，通过尝试获取连接来判断
            return False
        except Exception:
            return False

    async def add_documents(self, docs: list[Document]) -> list[str]:
        if not docs:
            return []

        texts = [d.content for d in docs]
        all_vectors = self._embedding_fn(texts) if self._embedding_fn else []
        if not all_vectors:
            return [d.id for d in docs]

        ids = [d.id or str(uuid.uuid4()) for d in docs]
        async with self._db_session_factory() as session:
            for i, doc in enumerate(docs):
                vec = all_vectors[i] if i < len(all_vectors) else []
                table = self._table_name
                id_col = self._id_col
                embed_json = {"v": vec}
                await session.execute(
                    f"UPDATE {table} SET embedding = :embed WHERE {id_col} = :id",
                    {"embed": embed_json, "id": doc.id},
                )
            await session.commit()

        return ids

    async def add_document(self, doc: Document) -> None:
        await self.add_documents([doc])

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """搜索相似文档。

        优先使用 pgvector 的 HNSW 索引（PostgreSQL），
        否则使用应用层余弦相似度（SQLite）。
        """
        query_vec = self._get_embedding(query)
        if not query_vec:
            return []

        async with self._db_session_factory() as session:
            try:
                return await self._search_pgvector(session, query_vec, top_k)
            except Exception:
                return await self._search_fallback(session, query_vec, top_k)

    async def _search_pgvector(self, session, query_vec: list[float], top_k: int) -> list[SearchResult]:
        """使用 pgvector HNSW 索引搜索（PostgreSQL 专用）。"""
        from sqlalchemy import text

        table = self._table_name
        id_col = self._id_col
        content_col = self._content_col

        sql = text(f"""
            SELECT {id_col} AS id, {content_col} AS content,
                   embedding_vector <=> :query_vec AS distance
            FROM {table}
            WHERE embedding_vector IS NOT NULL
            ORDER BY embedding_vector <=> :query_vec
            LIMIT :top_k
        """)
        result = await session.execute(sql, {
            "query_vec": str(query_vec),
            "top_k": top_k,
        })
        rows = result.fetchall()

        return [
            SearchResult(
                id=str(row[0]),
                content=str(row[1] or ""),
                metadata={},
                distance=float(row[2]),
            )
            for row in rows
        ]

    async def _search_fallback(self, session, query_vec: list[float], top_k: int) -> list[SearchResult]:
        """应用层余弦相似度（SQLite 降级）。"""
        from sqlalchemy import text

        table = self._table_name
        id_col = self._id_col
        content_col = self._content_col
        embed_col = self._embedding_col

        sql = text(f"""
            SELECT {id_col} AS id, {content_col} AS content, {embed_col} AS embedding
            FROM {table}
            WHERE {embed_col} IS NOT NULL
        """)
        result = await session.execute(sql)
        rows = result.fetchall()

        scored = []
        for row in rows:
            embed_data = row[2]
            if not embed_data:
                continue
            vec = embed_data.get("v") if isinstance(embed_data, dict) else embed_data
            if not vec:
                continue
            distance = 1.0 - _cosine_similarity(query_vec, vec)
            scored.append((distance, SearchResult(
                id=str(row[0]),
                content=str(row[1] or ""),
                metadata={},
                distance=distance,
            )))

        scored.sort(key=lambda x: x[0])
        return [sr for _, sr in scored[:top_k]]

    async def persist(self) -> None:
        logger.info("PgVectorStore: 持久化由 PG 自动管理，无需额外操作")


# 保留别名确保向后兼容
ChromaVectorStore = PgVectorStore
