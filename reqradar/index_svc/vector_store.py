"""向量存储 — ChromaDB 内置嵌入函数。"""

from __future__ import annotations

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

logger = logging.getLogger("reqradar.vector_store")

try:
    import chromadb
    from chromadb.utils import embedding_functions as chroma_ef

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    chromadb = None
    chroma_ef = None


def _get_index_version_path(persist_directory: Path) -> Path:
    """获取索引版本文件路径。"""
    return persist_directory / "version.json"


def _write_index_version(persist_directory: Path) -> None:
    """写入索引版本信息。"""
    version_path = _get_index_version_path(persist_directory)
    try:
        version_info = {
            "chromadb_version": chromadb.__version__ if chromadb else "unknown",
        }
        with open(version_path, "w", encoding="utf-8") as f:
            json.dump(version_info, f)
    except Exception:
        logger.warning("Failed to write index version file")


def _check_index_compatibility(persist_directory: Path) -> bool:
    """检查索引与当前 ChromaDB 版本的兼容性。"""
    version_path = _get_index_version_path(persist_directory)
    if not version_path.exists():
        return True
    try:
        with open(version_path, encoding="utf-8") as f:
            info = json.load(f)
        indexed_version = info.get("chromadb_version", "unknown")
        current_version = chromadb.__version__ if chromadb else "unknown"
        if indexed_version != current_version:
            logger.warning(
                "ChromaDB version mismatch: index created with %s, current is %s. "
                "Consider rebuilding the index: rm -rf %s && reqradar index",
                indexed_version,
                current_version,
                persist_directory,
            )
            return False
    except Exception:
        pass
    return True


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
    def add_document(self, doc: Document) -> None:
        """添加单个文档。"""

    @abstractmethod
    def add_documents(self, docs: list[Document]) -> None:
        """批量添加文档。"""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """搜索相似文档。"""

    @abstractmethod
    def persist(self) -> None:
        """持久化数据到磁盘。"""


def _estimate_model_size_mb(model_name: str) -> int:
    """估算嵌入模型大小。"""
    try:
        from reqradar.infrastructure.config import EMBEDDING_MODELS

        info = EMBEDDING_MODELS.get(model_name)
        return info["size_mb"] if info else 400
    except ImportError:
        return 400


def _create_embedding_function(
    embedding_model: str,
    use_onnx: bool = False,
    model_cache: str | None = None,
) -> object:
    """创建嵌入函数实例。

    优先使用 SentenceTransformerEmbeddingFunction（支持中文模型），
    失败时降级到 ChromaDB 内置 ONNXMiniLM_L6_V2。
    """
    if model_cache:
        os.environ["SENTENCE_TRANSFORMERS_HOME"] = model_cache

    try:
        ef = chroma_ef.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model,
        )
        logger.info(
            "使用 SentenceTransformerEmbeddingFunction (模型=%s)",
            embedding_model,
        )
        return ef
    except Exception as e:
        logger.warning(
            "SentenceTransformer 加载失败 (%s)，降级到内置 ONNXMiniLM_L6_V2。"
            "中文语义搜索质量会下降。",
            e,
        )
        return chroma_ef.ONNXMiniLM_L6_V2()


class ChromaVectorStore(VectorStore):
    """ChromaDB 持久化向量存储。"""

    _client_cache: dict[str, object] = {}

    def __init__(
        self,
        persist_directory: str = ".reqradar/vectorstore",
        embedding_model: str = "BAAI/bge-small-zh",
        collection_name: str = "requirements",
        model_cache: str | None = None,
        use_onnx: bool = False,
    ) -> None:
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "chromadb 未安装。请运行: pip install 'reqradar[vector]' 或 pip install chromadb"
            )

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        _check_index_compatibility(self.persist_directory)

        cache_key = str(self.persist_directory.resolve())
        try:
            if cache_key in ChromaVectorStore._client_cache:
                self.client = ChromaVectorStore._client_cache[cache_key]
            else:
                self.client = chromadb.PersistentClient(
                    path=str(self.persist_directory),
                    settings=chromadb.Settings(
                        anonymized_telemetry=False,
                    ),
                )
                ChromaVectorStore._client_cache[cache_key] = self.client
        except Exception as e:
            raise ImportError(
                f"ChromaDB 索引与当前版本不兼容。"
                f"请重建索引: rm -rf {self.persist_directory} && reqradar index。"
                f"原始错误: {e}"
            ) from e

        logger.info(
            "Loading embedding model '%s' (first run will download ~%d MB)...",
            embedding_model,
            _estimate_model_size_mb(embedding_model),
        )

        self.ef = _create_embedding_function(
            embedding_model=embedding_model,
            use_onnx=use_onnx,
            model_cache=model_cache,
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, docs: list[Document]) -> None:
        """批量添加文档。"""
        if not docs:
            return

        ids = [doc.id or str(uuid.uuid4()) for doc in docs]
        contents = [doc.content for doc in docs]
        metadatas = [doc.metadata if doc.metadata else None for doc in docs]

        self.collection.add(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
        )

    def add_document(self, doc: Document) -> None:
        """添加单个文档。"""
        self.add_documents([doc])

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """搜索相似文档。"""
        try:
            count = self.collection.count()
            if count == 0:
                return []
        except Exception:
            pass

        results = self.collection.query(
            query_texts=query,
            n_results=top_k,
        )

        search_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                search_results.append(
                    SearchResult(
                        id=results["ids"][0][i],
                        content=doc,
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        distance=results["distances"][0][i] if results["distances"] else 0.0,
                    )
                )

        return search_results

    def persist(self) -> None:
        """持久化数据到磁盘。"""
        _write_index_version(self.persist_directory)
        logger.info("Vector store persisted to %s", self.persist_directory)
