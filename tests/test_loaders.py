"""测试加载器基类和注册表"""

from pathlib import Path

import pytest

from reqradar.core.exceptions import LoaderException
from reqradar.modules.loaders.base import (
    DocumentLoader,
    LoadedDocument,
    LoaderRegistry,
)


class DummyLoader(DocumentLoader):
    def supported_extensions(self) -> list[str]:
        return [".txt", ".md"]

    def load(self, file_path: Path, **kwargs) -> list[LoadedDocument]:
        return [LoadedDocument(content="test", source=str(file_path), format="text")]


class TestLoadedDocument:
    def test_default_fields(self):
        doc = LoadedDocument(content="hello", source="test.txt", format="text")
        assert doc.content == "hello"
        assert doc.metadata == {}
        assert doc.images == []

    def test_with_metadata(self):
        doc = LoadedDocument(
            content="hello",
            source="test.txt",
            format="text",
            metadata={"title": "Test"},
        )
        assert doc.metadata["title"] == "Test"


class TestLoaderRegistry:
    def setup_method(self):
        LoaderRegistry._loaders = {}

    def test_register_and_get(self):
        loader = DummyLoader()
        LoaderRegistry.register("dummy", loader)
        assert LoaderRegistry.get("dummy") is loader

    def test_get_unknown_raises(self):
        with pytest.raises(LoaderException, match="Unknown loader"):
            LoaderRegistry.get("nonexistent")

    def test_list_available(self):
        loader = DummyLoader()
        LoaderRegistry.register("dummy", loader)
        assert "dummy" in LoaderRegistry.list_available()

    def test_get_for_file(self):
        loader = DummyLoader()
        LoaderRegistry.register("dummy", loader)
        result = LoaderRegistry.get_for_file(Path("test.txt"))
        assert result is loader

    def test_get_for_unsupported_file(self):
        result = LoaderRegistry.get_for_file(Path("test.xyz"))
        assert result is None

    def test_supports_method(self):
        loader = DummyLoader()
        assert loader.supports(Path("test.txt")) is True
        assert loader.supports(Path("test.xyz")) is False


class TestMemoryConfig:
    def test_defaults(self):
        from reqradar.infrastructure.config import MemoryConfig

        config = MemoryConfig()
        assert config.enabled is True
        assert config.storage_path == ""


class TestLoaderConfig:
    def test_defaults(self):
        from reqradar.infrastructure.config import LoaderConfig

        config = LoaderConfig()
        assert config.chunk_size == 300
        assert config.pdf_enabled is True


class TestConfigWithNewFields:
    def test_config_includes_new_fields(self):
        from reqradar.infrastructure.config import Config

        config = Config()
        assert hasattr(config, "vision")
        assert hasattr(config, "memory")
        assert hasattr(config, "loader")
        assert config.vision.model == "gpt-4o"
        assert config.memory.enabled is True
