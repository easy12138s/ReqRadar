"""向量存储 - Chroma 嵌入式"""

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("reqradar.vector_store")

try:
    import chromadb
    import sentence_transformers

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    chromadb = None
    sentence_transformers = None


def _get_index_version_path(persist_directory: Path) -> Path:
    return persist_directory / "version.json"


def _write_index_version(persist_directory: Path):
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
    id: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    id: str
    content: str
    metadata: dict
    distance: float


class VectorStore(ABC):
    """向量存储基类"""

    @abstractmethod
    def add_document(self, doc: Document):
        pass

    @abstractmethod
    def add_documents(self, docs: list[Document]):
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        pass

    @abstractmethod
    def persist(self):
        pass


class ChromaVectorStore(VectorStore):
    """Chroma 持久化向量存储"""

    def __init__(
        self,
        persist_directory: str = ".reqradar/vectorstore",
        embedding_model: str = "BAAI/bge-large-zh",
        collection_name: str = "requirements",
    ):
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "chroma or sentence-transformers not installed. "
                "Run: pip install chromadb sentence-transformers"
            )

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        _check_index_compatibility(self.persist_directory)

        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=chromadb.Settings(
                    anonymized_telemetry=False,
                ),
            )
        except Exception as e:
            raise ImportError(
                f"ChromaDB index is incompatible with current version. "
                f"Please rebuild: rm -rf {self.persist_directory} && reqradar index. "
                f"Original error: {e}"
            ) from e

        self.embedding_model = sentence_transformers.SentenceTransformer(embedding_model)

        self.collection = self.client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def add_documents(self, docs: list[Document]):
        """批量添加文档"""
        if not docs:
            return

        ids = [doc.id or str(uuid.uuid4()) for doc in docs]
        contents = [doc.content for doc in docs]
        metadatas = [doc.metadata if doc.metadata else None for doc in docs]
        embeddings = self.embedding_model.encode(contents).tolist()

        self.collection.add(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def add_document(self, doc: Document):
        """添加单个文档"""
        self.add_documents([doc])

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """搜索相似文档"""
        try:
            count = self.collection.count()
            if count == 0:
                return []
        except Exception:
            pass

        query_embedding = self.embedding_model.encode([query]).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
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

    def persist(self):
        """持久化数据到磁盘（PersistentClient 自动持久化，此方法保留接口兼容）"""
        _write_index_version(self.persist_directory)
        logger.info("Vector store persisted to %s", self.persist_directory)
