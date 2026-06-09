"""Markdown 切分器 — 按标题/段落切分为结构化 Chunk。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ChunkData:
    """文档 Chunk 的结构化数据。"""

    chunk_type: str  # paragraph / section / heading / table / list
    content: str
    position: int
    offset_start: int
    offset_end: int
    section_path: str | None = None


class MarkdownChunker:
    """Markdown 按标题层级切分。"""

    MIN_CHUNK_LENGTH: int = 50  # 过短 chunk 合并到前一个

    def chunk(self, markdown_text: str) -> list[ChunkData]:
        """将 Markdown 文本切分为 Chunk 列表。

        Args:
            markdown_text: Markdown 格式文本

        Returns:
            ChunkData 列表
        """
        if not markdown_text.strip():
            return []

        # 按标题分割
        sections: list[tuple[str, str]] = self._split_by_headings(markdown_text)

        chunks: list[ChunkData] = []
        offset = 0

        for i, (heading, body) in enumerate(sections):
            if heading:
                chunks.append(
                    ChunkData(
                        chunk_type="heading",
                        content=heading.strip(),
                        position=i * 2,
                        offset_start=offset,
                        offset_end=offset + len(heading),
                        section_path=self._extract_section_path(heading),
                    )
                )
                offset += len(heading)

            if body.strip():
                body_chunks = self._split_body(body, position_base=i * 2 + 1, offset_base=offset)
                for bc in body_chunks:
                    if heading and not bc.section_path:
                        bc.section_path = self._extract_section_path(heading)
                chunks.extend(body_chunks)
                offset += len(body)

        # 合并过短 chunk
        chunks = self._merge_short_chunks(chunks)

        return chunks

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """按 Markdown 标题分割文本。"""
        pattern = r"(^#{1,6}\s+.+$)"
        lines = text.split("\n")
        sections: list[tuple[str, str]] = []
        current_heading = ""
        current_body: list[str] = []

        for line in lines:
            if re.match(pattern, line):
                if current_heading or current_body:
                    sections.append((current_heading, "\n".join(current_body)))
                current_heading = line + "\n"
                current_body = []
            else:
                current_body.append(line)

        if current_heading or current_body:
            sections.append((current_heading, "\n".join(current_body)))

        return sections if sections else [("", text)]

    def _split_body(
        self, body: str, position_base: int, offset_base: int
    ) -> list[ChunkData]:
        """将正文按段落切分。"""
        chunks: list[ChunkData] = []
        paragraphs = body.split("\n\n")
        offset = offset_base

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                offset += 2  # \n\n
                continue

            chunk_type = self._detect_chunk_type(para)

            chunks.append(
                ChunkData(
                    chunk_type=chunk_type,
                    content=para,
                    position=position_base + i,
                    offset_start=offset,
                    offset_end=offset + len(para),
                )
            )
            offset += len(para) + 2  # +2 for \n\n

        return chunks

    @staticmethod
    def _detect_chunk_type(text: str) -> str:
        """检测段落类型。"""
        if text.startswith("|") and "|" in text[2:]:
            return "table"
        if text.startswith(("- ", "* ", "1. ", "2. ")):
            return "list"
        if text.startswith("```"):
            return "section"
        return "paragraph"

    @staticmethod
    def _extract_section_path(heading: str) -> str:
        """从标题提取路径。"""
        heading = heading.strip().lstrip("#").strip()
        return heading

    def _merge_short_chunks(self, chunks: list[ChunkData]) -> list[ChunkData]:
        """合并过短的 chunk 到前一个。"""
        if not chunks:
            return chunks

        merged: list[ChunkData] = []
        for chunk in chunks:
            if (
                merged
                and len(chunk.content) < self.MIN_CHUNK_LENGTH
                and merged[-1].chunk_type != "heading"
            ):
                prev = merged[-1]
                prev.content += "\n" + chunk.content
                prev.offset_end = chunk.offset_end
            else:
                merged.append(chunk)

        return merged
