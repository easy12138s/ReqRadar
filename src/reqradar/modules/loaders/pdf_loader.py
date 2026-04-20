"""PDF 文件加载器"""

import logging
from pathlib import Path

from reqradar.modules.loaders.base import DocumentLoader, LoadedDocument, chunk_text

logger = logging.getLogger("reqradar.loaders.pdf")

try:
    import pdfplumber

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


class PDFLoader(DocumentLoader):
    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 50):
        if not PDF_AVAILABLE:
            raise ImportError("pdfplumber is not installed. Run: pip install pdfplumber")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def load(self, file_path: Path, **kwargs) -> list[LoadedDocument]:
        chunk_size = kwargs.get("chunk_size", self.chunk_size)
        chunk_overlap = kwargs.get("chunk_overlap", self.chunk_overlap)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        full_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"

        if not full_text.strip():
            logger.warning("No text extracted from PDF: %s", file_path)
            return []

        chunks = chunk_text(full_text, chunk_size=chunk_size, overlap=chunk_overlap)

        return [
            LoadedDocument(
                content=chunk,
                source=str(file_path),
                format="pdf",
                metadata={"title": file_path.stem, "chunk_index": i},
            )
            for i, chunk in enumerate(chunks)
        ]

