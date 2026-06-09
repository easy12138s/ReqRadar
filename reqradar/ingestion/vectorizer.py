"""Vectorizer — ChromaDB 向量化，复用 ChromaVectorStore。

为 requirements 和 code 两个集合提供向量化能力：
  - requirements: 文档 chunk 集合
  - code: 代码模块集合

使用 threading.Lock 保护 ChromaDB 写入（PersistentClient 不支持并发写入）。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from reqradar.index_svc.vector_store import ChromaVectorStore, Document

logger = logging.getLogger(__name__)

# 全局写入锁（ChromaDB PersistentClient 不支持多进程/多线程并发写入）
_write_lock = threading.Lock()


@dataclass
class VectorizeInput:
    """向量化输入数据。"""

    id: str
    content: str
    metadata: dict | None = None


class IngestionVectorizer:
    """ChromaDB 向量化 — 复用 ChromaVectorStore，支持 requirements/code 两个集合。"""

    COLLECTION_REQUIREMENTS = "requirements"
    COLLECTION_CODE = "code"

    def __init__(
        self,
        persist_directory: str = ".reqradar/vectorstore",
        use_onnx: bool = True,
    ) -> None:
        """初始化向量化器。

        Args:
            persist_directory: ChromaDB 持久化目录
            use_onnx: 是否使用 ONNX 模型（零下载，秒启动）
        """
        self._persist_directory = persist_directory
        self._use_onnx = use_onnx

    def vectorize_chunks(self, chunks: list[VectorizeInput]) -> list[str]:
        """将文档 Chunk 向量化写入 requirements 集合。

        Args:
            chunks: Chunk 数据列表

        Returns:
            embedding_id 列表（与输入顺序对应）
        """
        if not chunks:
            return []

        store = ChromaVectorStore(
            persist_directory=self._persist_directory,
            collection_name=self.COLLECTION_REQUIREMENTS,
            use_onnx=self._use_onnx,
        )

        docs = [
            Document(id=chunk.id, content=chunk.content, metadata=chunk.metadata)
            for chunk in chunks
        ]

        with _write_lock:
            embedding_ids = store.add_documents(docs)

        return embedding_ids

    def vectorize_code_modules(self, modules: list[VectorizeInput]) -> list[str]:
        """将代码模块向量化写入 code 集合。

        Args:
            modules: 代码模块数据列表

        Returns:
            embedding_id 列表（与输入顺序对应）
        """
        if not modules:
            return []

        store = ChromaVectorStore(
            persist_directory=self._persist_directory,
            collection_name=self.COLLECTION_CODE,
            use_onnx=self._use_onnx,
        )

        docs = [
            Document(id=module.id, content=module.content, metadata=module.metadata)
            for module in modules
        ]

        with _write_lock:
            embedding_ids = store.add_documents(docs)

        return embedding_ids

    def close(self) -> None:
        """释放 ChromaDB 资源（operations_log 等）。"""
        # ChromaDB PersistentClient 的 HTTP 客户端会在 GC 时关闭
        # 这里主要确保日志刷新
        pass
