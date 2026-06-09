"""文档解析器单元测试 — markitdown 封装。"""

from __future__ import annotations

from pathlib import Path

import pytest

from reqradar.ingestion.parsers.document_parser import DocumentParser


class TestDocumentParser:
    """文档解析器测试。"""

    def test_parse_markdown_file(self, tmp_path: Path) -> None:
        """解析 .md 文件应返回 Markdown 文本。"""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n\nWorld", encoding="utf-8")
        parser = DocumentParser()
        result = parser.parse_file(md_file)
        assert "# Hello" in result
        assert "World" in result

    def test_parse_file_not_found(self) -> None:
        """文件不存在时抛出 IngestionException。"""
        parser = DocumentParser()
        with pytest.raises(Exception, match="文件不存在"):
            parser.parse_file(Path("/nonexistent/file.md"))

    def test_parse_bytes(self, tmp_path: Path) -> None:
        """字节流解析应正常返回。"""
        content = b"# Test\n\nContent"
        parser = DocumentParser()
        result = parser.parse_bytes(content, "test.md")
        assert "Test" in result
        assert "Content" in result
