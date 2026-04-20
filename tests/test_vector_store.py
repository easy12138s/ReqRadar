"""测试向量存储模块"""

import pytest

from reqradar.modules.vector_store import CHROMA_AVAILABLE, Document, SearchResult


class TestDocument:
    def test_create_with_required_fields(self):
        doc = Document(id="doc1", content="hello world")
        assert doc.id == "doc1"
        assert doc.content == "hello world"
        assert doc.metadata == {}

    def test_create_with_metadata(self):
        doc = Document(id="doc2", content="test", metadata={"source": "req", "page": 1})
        assert doc.metadata["source"] == "req"
        assert doc.metadata["page"] == 1

    def test_metadata_default_is_independent(self):
        doc1 = Document(id="a", content="a")
        doc2 = Document(id="b", content="b")
        doc1.metadata["key"] = "val"
        assert "key" not in doc2.metadata

    def test_equality(self):
        doc1 = Document(id="x", content="x", metadata={"k": "v"})
        doc2 = Document(id="x", content="x", metadata={"k": "v"})
        assert doc1 == doc2

    def test_inequality_different_id(self):
        doc1 = Document(id="a", content="same")
        doc2 = Document(id="b", content="same")
        assert doc1 != doc2

    def test_inequality_different_content(self):
        doc1 = Document(id="a", content="foo")
        doc2 = Document(id="a", content="bar")
        assert doc1 != doc2

    def test_empty_content(self):
        doc = Document(id="e", content="")
        assert doc.content == ""

    def test_metadata_empty_dict(self):
        doc = Document(id="m", content="c", metadata={})
        assert doc.metadata == {}


class TestSearchResult:
    def test_create(self):
        sr = SearchResult(id="s1", content="text", metadata={"src": "a"}, distance=0.42)
        assert sr.id == "s1"
        assert sr.content == "text"
        assert sr.metadata == {"src": "a"}
        assert sr.distance == 0.42

    def test_distance_zero(self):
        sr = SearchResult(id="s2", content="exact match", metadata={}, distance=0.0)
        assert sr.distance == 0.0

    def test_equality(self):
        sr1 = SearchResult(id="s", content="c", metadata={}, distance=0.1)
        sr2 = SearchResult(id="s", content="c", metadata={}, distance=0.1)
        assert sr1 == sr2


class TestChromaVectorStore:
    @pytest.fixture
    def store(self, tmp_path):
        chromadb = pytest.importorskip("chromadb")
        pytest.importorskip("sentence_transformers")
        from reqradar.modules.vector_store import ChromaVectorStore

        return ChromaVectorStore(
            persist_directory=str(tmp_path / "vectordb"),
            embedding_model="BAAI/bge-large-zh",
        )

    def test_init_creates_directory(self, tmp_path):
        pytest.importorskip("chromadb")
        pytest.importorskip("sentence_transformers")
        from reqradar.modules.vector_store import ChromaVectorStore

        db_path = tmp_path / "vectordb"
        store = ChromaVectorStore(persist_directory=str(db_path))
        assert db_path.exists()

    def test_init_raises_import_error_without_chroma(self, tmp_path, monkeypatch):
        if CHROMA_AVAILABLE:
            return
        from reqradar.modules.vector_store import ChromaVectorStore

        with pytest.raises(ImportError, match="chroma"):
            ChromaVectorStore(persist_directory=str(tmp_path / "vectordb"))

    def test_add_document_single(self, store):
        doc = Document(id="d1", content="用户认证模块", metadata={"module": "auth"})
        store.add_document(doc)
        results = store.search("认证", top_k=1)
        assert len(results) >= 1
        assert results[0].id == "d1"
        assert results[0].content == "用户认证模块"
        assert results[0].metadata["module"] == "auth"

    def test_add_documents_batch(self, store):
        docs = [
            Document(id="d1", content="用户登录功能", metadata={"type": "feature"}),
            Document(id="d2", content="数据加密存储", metadata={"type": "security"}),
            Document(id="d3", content="接口限流策略", metadata={"type": "reliability"}),
        ]
        store.add_documents(docs)
        results = store.search("加密", top_k=3)
        assert len(results) >= 1
        assert any(r.id == "d2" for r in results)

    def test_add_documents_empty_list(self, store):
        store.add_documents([])

    def test_add_document_auto_uuid(self, store):
        doc = Document(id="", content="自动ID文档", metadata={})
        store.add_document(doc)
        results = store.search("自动ID", top_k=1)
        assert len(results) == 1

    def test_search_empty_collection(self, store):
        results = store.search("不存在的查询", top_k=5)
        assert results == []

    def test_search_top_k(self, store):
        docs = [Document(id=f"d{i}", content=f"需求文档{i}", metadata={}) for i in range(5)]
        store.add_documents(docs)
        results = store.search("需求", top_k=3)
        assert len(results) <= 3

    def test_search_result_fields(self, store):
        doc = Document(id="field-test", content="权限管理模块", metadata={"owner": "张三"})
        store.add_document(doc)
        results = store.search("权限", top_k=1)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, SearchResult)
        assert isinstance(r.id, str)
        assert isinstance(r.content, str)
        assert isinstance(r.metadata, dict)
        assert isinstance(r.distance, float)

    def test_persist(self, store):
        store.persist()

    def test_search_returns_sorted_by_distance(self, store):
        docs = [
            Document(id="close", content="用户认证系统", metadata={}),
            Document(id="far", content="服务器部署流程", metadata={}),
        ]
        store.add_documents(docs)
        results = store.search("认证", top_k=2)
        if len(results) == 2:
            assert results[0].distance <= results[1].distance

    def test_add_and_search_round_trip(self, tmp_path):
        pytest.importorskip("chromadb")
        pytest.importorskip("sentence_transformers")
        from reqradar.modules.vector_store import ChromaVectorStore

        path1 = str(tmp_path / "db1")
        store1 = ChromaVectorStore(persist_directory=path1)
        store1.add_documents([
            Document(id="req-1", content="实现OAuth2认证", metadata={"priority": "high"}),
            Document(id="req-2", content="数据库迁移方案", metadata={"priority": "medium"}),
        ])
        store1.persist()

        store2 = ChromaVectorStore(persist_directory=path1)
        results = store2.search("OAuth2", top_k=2)
        assert len(results) >= 1
        assert results[0].id == "req-1"


class TestCHROMA_AVAILABLEFlag:
    def test_flag_is_boolean(self):
        assert isinstance(CHROMA_AVAILABLE, bool)
