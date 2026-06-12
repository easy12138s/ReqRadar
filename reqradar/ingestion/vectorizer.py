"""Vectorizer — 嵌入向量计算，直接写入 PG embedding 列。

替代 ChromaDB 写入流程：
  1. 调用 API Embedding 计算向量
  2. 直接 UPDATE 实体表的 embedding JSON 列

不再需要 ChromaDB 集合和 threading.Lock。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VectorizeInput:
    """向量化输入数据。"""

    id: str
    content: str
    metadata: dict | None = None


@dataclass
class VectorizeResult:
    """向量化结果 — 每个输入对应的嵌入向量。"""

    id: str
    vector: list[float]


class IngestionVectorizer:
    """嵌入向量计算器 — 通过 API 计算向量，写入 PG 实体的 embedding 列。

    不与具体存储后端耦合，仅负责任务：
      1. 接收待向量化的文本列表
      2. 调用 ReqRadarEmbeddingFunction（API 模式）
      3. 返回向量结果供调用方写入 PG embedding 列
    """

    def __init__(self, embedding_fn=None) -> None:
        self._embedding_fn = embedding_fn

    def _get_embedding_fn(self):
        if self._embedding_fn is None:
            from reqradar.kernel.embedding import ReqRadarEmbeddingFunction
            self._embedding_fn = ReqRadarEmbeddingFunction()
        return self._embedding_fn

    def vectorize(self, inputs: list[VectorizeInput]) -> list[VectorizeResult]:
        """计算一批文本的嵌入向量。

        Args:
            inputs: 待向量化的数据列表

        Returns:
            向量化结果列表（与输入顺序一致）
        """
        if not inputs:
            return []

        texts = [item.content for item in inputs]
        ef = self._get_embedding_fn()
        vectors = ef(texts)

        return [
            VectorizeResult(id=inputs[i].id, vector=vectors[i])
            for i in range(len(inputs))
        ]

    def vectorize_chunks(self, chunks: list[VectorizeInput]) -> list[str]:
        """（兼容接口）向量化 Chunk 并返回 ID 列表。

        返回的 ID 列表与 chunks 输入顺序一致。
        实际写入由调用方通过 UPDATE embedding 列完成。
        """
        results = self.vectorize(chunks)
        return [r.id for r in results]

    def vectorize_code_modules(self, modules: list[VectorizeInput]) -> list[str]:
        """（兼容接口）向量化代码模块并返回 ID 列表。"""
        return self.vectorize_chunks(modules)
