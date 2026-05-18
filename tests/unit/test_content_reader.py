from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reqradar.web.services.content_reader import _TRUNCATE_LENGTH, ContentReader


@pytest.fixture
def content_reader():
    session_factory = MagicMock()
    report_storage = MagicMock()
    return ContentReader(
        session_factory=session_factory,
        report_storage=report_storage,
        memory_storage_path="/tmp/test_memories",
    )


class TestContentReaderInit:
    def test_initialization(self):
        sf = MagicMock()
        rs = MagicMock()
        reader = ContentReader(session_factory=sf, report_storage=rs, memory_storage_path="/path")
        assert reader._session_factory is sf
        assert reader._report_storage is rs
        assert reader._memory_storage_path == "/path"


class TestReadReportMarkdown:
    @pytest.mark.asyncio
    async def test_read_without_version(self, content_reader):
        content_reader._report_storage.read_report = AsyncMock(
            return_value=("markdown content", {})
        )
        result = await content_reader.read_report_markdown(100)
        assert result == "markdown content"

    @pytest.mark.asyncio
    async def test_read_with_version(self, content_reader):
        content_reader._report_storage.read_version = AsyncMock(return_value=("v2 markdown", {}))
        result = await content_reader.read_report_markdown(100, version=2)
        assert result == "v2 markdown"

    @pytest.mark.asyncio
    async def test_read_report_not_found(self, content_reader):
        content_reader._report_storage.read_report = AsyncMock(return_value=(None, None))
        result = await content_reader.read_report_markdown(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_read_version_not_found(self, content_reader):
        content_reader._report_storage.read_version = AsyncMock(return_value=(None, None))
        result = await content_reader.read_report_markdown(100, version=99)
        assert result is None


class TestReadProjectMemory:
    @pytest.mark.asyncio
    async def test_calls_project_memory_load(self, content_reader):
        with patch("reqradar.web.services.content_reader.ProjectMemory") as mock_memory_cls:
            mock_memory_instance = MagicMock()
            mock_memory_instance.load.return_value = {"terminology": {}}
            mock_memory_cls.return_value = mock_memory_instance

            result = await content_reader.read_project_memory(10)
            assert result == {"terminology": {}}
            mock_memory_cls.assert_called_once_with("/tmp/test_memories", 10)

    @pytest.mark.asyncio
    async def test_no_memory_file(self, content_reader):
        with patch("reqradar.web.services.content_reader.ProjectMemory") as mock_memory_cls:
            mock_memory_instance = MagicMock()
            mock_memory_instance.load.return_value = None
            mock_memory_cls.return_value = mock_memory_instance

            result = await content_reader.read_project_memory(999)
            assert result is None


class TestReadRequirementContent:
    @pytest.mark.asyncio
    async def test_returns_document_fields(self, content_reader):
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.title = "Test Doc"
        mock_doc.consolidated_text = "doc content"
        mock_doc.status = "ready"
        mock_doc.version = 1

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await content_reader.read_requirement_content(1)
        assert result == {
            "id": 1,
            "title": "Test Doc",
            "content": "doc content",
            "status": "ready",
            "version": 1,
        }

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, content_reader):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await content_reader.read_requirement_content(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_none_consolidated_text(self, content_reader):
        mock_doc = MagicMock()
        mock_doc.id = 2
        mock_doc.title = "Empty"
        mock_doc.consolidated_text = None
        mock_doc.status = "ready"
        mock_doc.version = 1

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await content_reader.read_requirement_content(2)
        assert result["content"] == ""


class TestGetRequirementContext:
    @pytest.mark.asyncio
    async def test_returns_context_for_published_release(self, content_reader):
        mock_release = MagicMock()
        mock_release.id = 10
        mock_release.release_code = "REL-001"
        mock_release.version = 1
        mock_release.title = "Published Release"
        mock_release.content = "full content"
        mock_release.context_json = {"key": "value"}

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_release
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await content_reader.get_requirement_context(10)
        assert result["id"] == 10
        assert result["content"] == "full content"
        assert result["context_json"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_returns_none_for_non_published(self, content_reader):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await content_reader.get_requirement_context(99)
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_none_content(self, content_reader):
        mock_release = MagicMock()
        mock_release.id = 11
        mock_release.release_code = "REL-002"
        mock_release.version = 2
        mock_release.title = "No Content"
        mock_release.content = None
        mock_release.context_json = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_release
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await content_reader.get_requirement_context(11)
        assert result["content"] == ""
        assert result["context_json"] == {}


class TestReadContextJson:
    @pytest.mark.asyncio
    async def test_returns_context_json(self, content_reader):
        mock_task = MagicMock()
        mock_task.context_json = {"depth": "standard", "focus": "security"}

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await content_reader.read_context_json(1)
        assert result == {"depth": "standard", "focus": "security"}

    @pytest.mark.asyncio
    async def test_returns_none_when_task_not_found(self, content_reader):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        result = await content_reader.read_context_json(999)
        assert result is None


class TestSearchPublishedRequirements:
    def _make_release_row(self, **overrides):
        row = MagicMock()
        row.id = overrides.get("id", 1)
        row.project_id = overrides.get("project_id", 10)
        row.release_code = overrides.get("release_code", "REL-001")
        row.version = overrides.get("version", 1)
        row.title = overrides.get("title", "Test Release")
        row.content = overrides.get("content", "Some content")
        row.published_at = overrides.get("published_at")
        return row

    def _setup_session_with_rows(self, content_reader, rows):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session

    @pytest.mark.asyncio
    async def test_returns_published_releases(self, content_reader):
        rows = [
            self._make_release_row(id=1, title="Auth Module", content="Auth spec"),
            self._make_release_row(id=2, title="Payment Module", content="Payment spec"),
        ]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements()
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["title"] == "Auth Module"

    @pytest.mark.asyncio
    async def test_filters_by_project_id(self, content_reader):
        rows = [self._make_release_row(id=1, project_id=5)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements(project_id=5)
        assert len(result) == 1
        assert result[0]["project_id"] == 5

    @pytest.mark.asyncio
    async def test_filters_by_query(self, content_reader):
        rows = [self._make_release_row(id=1, title="Auth Module")]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements(query="Auth")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty_results(self, content_reader):
        self._setup_session_with_rows(content_reader, [])

        result = await content_reader.search_published_requirements()
        assert result == []

    @pytest.mark.asyncio
    async def test_content_truncated_at_threshold(self, content_reader):
        long_content = "x" * (_TRUNCATE_LENGTH + 200)
        rows = [self._make_release_row(id=1, content=long_content)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements()
        assert len(result[0]["content"]) == _TRUNCATE_LENGTH

    @pytest.mark.asyncio
    async def test_content_under_truncation_length_not_truncated(self, content_reader):
        short_content = "x" * 100
        rows = [self._make_release_row(id=1, content=short_content)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements()
        assert len(result[0]["content"]) == 100

    @pytest.mark.asyncio
    async def test_content_exactly_at_truncation_length(self, content_reader):
        exact_content = "x" * _TRUNCATE_LENGTH
        rows = [self._make_release_row(id=1, content=exact_content)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements()
        assert len(result[0]["content"]) == _TRUNCATE_LENGTH

    @pytest.mark.asyncio
    async def test_none_content_returns_empty_string(self, content_reader):
        rows = [self._make_release_row(id=1, content=None)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements()
        assert result[0]["content"] == ""

    @pytest.mark.asyncio
    async def test_ilike_special_chars_in_query(self, content_reader):
        rows = [self._make_release_row(id=1, title="100%_Complete")]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements(query="100%_Complete")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_published_at_iso_format(self, content_reader):
        pub_time = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        rows = [self._make_release_row(id=1, published_at=pub_time)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements()
        assert result[0]["published_at"] == pub_time.isoformat()

    @pytest.mark.asyncio
    async def test_published_at_none(self, content_reader):
        rows = [self._make_release_row(id=1, published_at=None)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.search_published_requirements()
        assert result[0]["published_at"] is None


class TestListAnalyses:
    def _make_task_row(self, **overrides):
        row = MagicMock()
        row.id = overrides.get("id", 1)
        row.project_id = overrides.get("project_id", 10)
        row.requirement_name = overrides.get("requirement_name", "Test Req")
        row.status = overrides.get("status", "completed")
        row.depth = overrides.get("depth", "standard")
        row.created_at = overrides.get("created_at", datetime(2026, 1, 1, tzinfo=UTC))
        return row

    def _setup_session_with_rows(self, content_reader, rows):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        content_reader._session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session

    @pytest.mark.asyncio
    async def test_returns_analysis_tasks(self, content_reader):
        rows = [
            self._make_task_row(id=1, requirement_name="Auth Analysis"),
            self._make_task_row(id=2, requirement_name="Payment Analysis"),
        ]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.list_analyses(project_id=10)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["requirement_name"] == "Auth Analysis"

    @pytest.mark.asyncio
    async def test_filters_by_status(self, content_reader):
        rows = [self._make_task_row(id=1, status="completed")]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.list_analyses(project_id=10, status="completed")
        assert len(result) == 1
        assert result[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_empty_results(self, content_reader):
        self._setup_session_with_rows(content_reader, [])

        result = await content_reader.list_analyses(project_id=999)
        assert result == []

    @pytest.mark.asyncio
    async def test_created_at_iso_format(self, content_reader):
        created = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        rows = [self._make_task_row(id=1, created_at=created)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.list_analyses(project_id=10)
        assert result[0]["created_at"] == created.isoformat()

    @pytest.mark.asyncio
    async def test_none_created_at(self, content_reader):
        rows = [self._make_task_row(id=1, created_at=None)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.list_analyses(project_id=10)
        assert result[0]["created_at"] is None

    @pytest.mark.asyncio
    async def test_respects_limit(self, content_reader):
        rows = [self._make_task_row(id=i) for i in range(3)]
        self._setup_session_with_rows(content_reader, rows)

        result = await content_reader.list_analyses(project_id=10, limit=3)
        assert len(result) == 3
