"""测试加载器注册表集成"""

from pathlib import Path

import pytest

from reqradar.modules.loaders.base import LoaderRegistry
from reqradar.modules.loaders import get_loader


class TestLoaderRegistryIntegration:
    def test_text_loader_registered(self):
        loader = LoaderRegistry.get("text")
        assert loader is not None
        assert loader.supports(Path("test.md"))

    def test_image_loader_registered(self):
        loader = LoaderRegistry.get("image")
        assert loader is not None
        assert loader.supports(Path("test.png"))

    def test_chat_loader_registered(self):
        loader = LoaderRegistry.get("chat")
        assert loader is not None

    def test_get_loader_by_file_extension(self):
        assert LoaderRegistry.get_for_file(Path("readme.md")) is not None
        assert LoaderRegistry.get_for_file(Path("doc.txt")) is not None
        assert LoaderRegistry.get_for_file(Path("data.json")) is None
        assert LoaderRegistry.get_for_file(Path("chat.csv")) is not None

    def test_feishu_json_by_name(self):
        loader = LoaderRegistry.get_for_file(Path("feishu_export.json"))
        assert loader is not None

    def test_get_loader_helper(self):
        loader = get_loader(Path("test.txt"))
        assert loader is not None

    def test_list_available(self):
        available = LoaderRegistry.list_available()
        assert "text" in available
        assert "image" in available
        assert "chat" in available
