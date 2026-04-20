"""测试文本加载器"""

from pathlib import Path

import pytest

from reqradar.modules.loaders.base import chunk_text
from reqradar.modules.loaders.text_loader import TextLoader


class TestTextLoader:
    def test_supported_extensions(self):
        loader = TextLoader()
        assert ".md" in loader.supported_extensions()
        assert ".txt" in loader.supported_extensions()
        assert ".rst" in loader.supported_extensions()

    def test_supports_method(self):
        loader = TextLoader()
        assert loader.supports(Path("test.md")) is True
        assert loader.supports(Path("test.txt")) is True
        assert loader.supports(Path("test.pdf")) is False

    def test_load_markdown_file(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nThis is a test document.", encoding="utf-8")

        loader = TextLoader()
        docs = loader.load(md_file)

        assert len(docs) >= 1
        assert docs[0].format == "text"
        assert docs[0].source == str(md_file)
        assert "test document" in docs[0].content.lower()

    def test_load_txt_file(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world", encoding="utf-8")

        loader = TextLoader()
        docs = loader.load(txt_file)

        assert len(docs) == 1
        assert "Hello world" in docs[0].content

    def test_load_nonexistent_file(self):
        loader = TextLoader()
        with pytest.raises(FileNotFoundError):
            loader.load(Path("/nonexistent/file.md"))

    def test_load_with_custom_chunk_size(self, tmp_path):
        txt_file = tmp_path / "long.txt"
        txt_file.write_text("A" * 1000, encoding="utf-8")

        loader = TextLoader(chunk_size=200, chunk_overlap=20)
        docs = loader.load(txt_file)

        assert len(docs) > 1

    def test_chunk_kwargs_override(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("A" * 1000, encoding="utf-8")

        loader = TextLoader(chunk_size=300)
        docs = loader.load(txt_file, chunk_size=100)

        assert len(docs) > 3


class TestChunkText:
    def test_short_text(self):
        result = chunk_text("hello", chunk_size=300)
        assert result == ["hello"]

    def test_long_text(self):
        result = chunk_text("A" * 1000, chunk_size=300, overlap=50)
        assert len(result) > 1

    def test_overlap_marker(self):
        result = chunk_text("A" * 1000, chunk_size=300, overlap=50)
        assert any("[接上文]" in chunk for chunk in result[1:])
