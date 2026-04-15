"""文本文件加载器 - 支持 .md, .txt, .rst"""

import logging
from pathlib import Path

from reqradar.modules.loaders.base import DocumentLoader, LoadedDocument

logger = logging.getLogger("reqradar.loaders.text")


class TextLoader(DocumentLoader):
    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def supported_extensions(self) -> list[str]:
        return [".md", ".txt", ".rst"]

    def load(self, file_path: Path, **kwargs) -> list[LoadedDocument]:
        chunk_size = kwargs.get("chunk_size", self.chunk_size)
        chunk_overlap = kwargs.get("chunk_overlap", self.chunk_overlap)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="gbk")

        chunks = _chunk_text(content, chunk_size=chunk_size, overlap=chunk_overlap)

        return [
            LoadedDocument(
                content=chunk,
                source=str(file_path),
                format="text",
                metadata={"title": file_path.stem, "chunk_index": i},
            )
            for i, chunk in enumerate(chunks)
        ]


def _chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if start > 0:
            chunk = f"[接上文]\n{chunk}"
        chunks.append(chunk)
        start = end - overlap
    return chunks
