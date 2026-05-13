"""ContentReader 服务单元测试"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from reqradar.web.services.content_reader import ContentReader


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
        content_reader._report_storage.read_report = AsyncMock(return_value=("markdown content", {}))
        result = await content_reader.read_report_markdown(100)
        assert result == "markdown content"

    @pytest.mark.asyncio
    async def test_read_with_version(self, content_reader):
        content_reader._report_storage.read_version = AsyncMock(return_value=("v2 markdown", {}))
        result = await content_reader.read_report_markdown(100, version=2)
        assert result == "v2 markdown"


class TestReadProjectMemory:
    @pytest.mark.asyncio
    async def test_calls_project_memory_load(self, content_reader):
        with patch("reqradar.web.services.content_reader.ProjectMemory") as MockMemory:
            mock_memory_instance = MagicMock()
            mock_memory_instance.load.return_value = {"terminology": {}}
            MockMemory.return_value = mock_memory_instance

            result = await content_reader.read_project_memory(10)
            assert result == {"terminology": {}}
            MockMemory.assert_called_once_with("/tmp/test_memories", 10)

    @pytest.mark.asyncio
    async def test_no_memory_file(self, content_reader):
        with patch("reqradar.web.services.content_reader.ProjectMemory") as MockMemory:
            mock_memory_instance = MagicMock()
            mock_memory_instance.load.return_value = None
            MockMemory.return_value = mock_memory_instance

            result = await content_reader.read_project_memory(999)
            assert result is None
