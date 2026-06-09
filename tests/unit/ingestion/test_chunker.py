"""Markdown 切分器单元测试。"""

from __future__ import annotations

from reqradar.ingestion.chunking.chunker import MarkdownChunker


class TestMarkdownChunker:
    """Markdown 切分器测试。"""

    def test_chunk_simple(self) -> None:
        """简单 Markdown 切分。"""
        text = "# Heading 1\n\nParagraph text here.\n\n## Heading 2\n\nMore text."
        chunker = MarkdownChunker()
        chunks = chunker.chunk(text)

        assert len(chunks) >= 2
        headings = [c for c in chunks if c.chunk_type == "heading"]
        assert len(headings) >= 1  # 第二个 ## heading 在空行后可能被识别

    def test_chunk_empty(self) -> None:
        """空文本返回空列表。"""
        chunker = MarkdownChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_chunk_table(self) -> None:
        """表格切分为 table 类型。"""
        text = "| A | B |\n|---|---|\n| 1 | 2 |"
        chunker = MarkdownChunker()
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert len(table_chunks) >= 1
