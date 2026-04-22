"""向量存储 - Chroma 嵌入式"""

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
    ):
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "chroma or sentence-transformers not installed. "
                "Run: pip install chromadb sentence-transformers"
            )

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=chromadb.Settings(
                anonymized_telemetry=False,
            ),
        )

        self.embedding_model = sentence_transformers.SentenceTransformer(embedding_model)

        self.collection = self.client.get_or_create_collection(
            name="requirements", metadata={"hnsw:space": "cosine"}
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
        logger.info("Vector store persisted to %s", self.persist_directory)
