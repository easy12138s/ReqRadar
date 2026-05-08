"""测试加载器注册表集成"""

from pathlib import Path

import pytest

from reqradar.modules.loaders.base import LoaderRegistry
from reqradar.modules.loaders import get_loader
from reqradar.modules.loaders.text_loader import TextLoader
from reqradar.modules.loaders.chat_loader import ChatLoader

MARKITDOWN_AVAILABLE = False
try:
    from reqradar.modules.loaders.markitdown_loader import MarkitdownLoader

    MARKITDOWN_AVAILABLE = True
except ImportError:
    pass


class TestLoaderRegistryIntegration:
    def setup_method(self):
        LoaderRegistry._loaders = {}
        LoaderRegistry.register("text", TextLoader())
        LoaderRegistry.register("chat", ChatLoader())
        if MARKITDOWN_AVAILABLE:
            LoaderRegistry.register("markitdown", MarkitdownLoader())

    def test_text_loader_registered(self):
        loader = LoaderRegistry.get("text")
        assert loader is not None
        assert loader.supports(Path("test.md"))

    def test_markitdown_loader_registered(self):
        if not MARKITDOWN_AVAILABLE:
            pytest.skip("markitdown not installed")
        loader = LoaderRegistry.get("markitdown")
        assert loader is not None
        assert loader.supports(Path("test.pdf"))
        assert loader.supports(Path("test.docx"))

    def test_chat_loader_registered(self):
        loader = LoaderRegistry.get("chat")
        assert loader is not None

    def test_get_loader_by_file_extension(self):
        assert LoaderRegistry.get_for_file(Path("readme.md")) is not None
        assert LoaderRegistry.get_for_file(Path("doc.txt")) is not None
        assert LoaderRegistry.get_for_file(Path("chat.csv")) is not None
        if MARKITDOWN_AVAILABLE:
            assert LoaderRegistry.get_for_file(Path("report.pdf")) is not None

    def test_feishu_json_by_name(self):
        loader = LoaderRegistry.get_for_file(Path("feishu_export.json"))
        assert loader is not None

    def test_get_loader_helper(self):
        loader = get_loader(Path("test.txt"))
        assert loader is not None

    def test_list_available(self):
        available = LoaderRegistry.list_available()
        assert "text" in available
        assert "chat" in available
        if MARKITDOWN_AVAILABLE:
            assert "markitdown" in available
