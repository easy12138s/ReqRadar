"""MarkItDown 统一文档加载器

基于 Microsoft MarkItDown，将 PDF/DOCX/PPTX/XLSX/HTML/图片/EPUB 等
格式统一转换为 Markdown，并自然分块。
"""

import logging
import re
from pathlib import Path
from typing import Optional

from reqradar.modules.loaders.base import DocumentLoader, LoadedDocument

logger = logging.getLogger("reqradar.loaders.markitdown")

try:
    from markitdown import MarkItDown

    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
    ".html",
    ".htm",
    ".epub",
    ".csv",
    ".json",
    ".xml",
}

ALL_EXTENSIONS = sorted(_IMAGE_EXTENSIONS | _DOCUMENT_EXTENSIONS)


def _split_by_headings(text: str) -> list[str]:
    """按标题自然分块：## Markdown / # Markdown / 中文编号 / 数字编号。"""
    if not text.strip():
        return [text]

    # 中文编号：标准汉字 + CJK Compatibility Ideographs 变体
    cn_num = r"[\u2f00\u2f06\u2f09\u2f14\u2f18\u2f1d一二三四五六七八九十]+、"

    patterns = [
        r"##\s",  # Markdown h2
        r"#\s",  # Markdown h1
        cn_num,  # 中文编号：一、二、三、...⼀、⼆、
        r"\d+(?:\.\d+)+\s",  # 数字子编号：1.1, 2.3.1
    ]
    combined = "|".join(f"(?={p})" for p in patterns)
    parts = re.split(rf"\n({combined})", text)

    return [p.strip() for p in parts if p.strip()]


class MarkitdownLoader(DocumentLoader):
    """统一文档加载器，基于 Microsoft MarkItDown 转换文件为 Markdown。"""

    _default_instance: Optional["MarkitdownLoader"] = None

    def __init__(self, llm_client=None, llm_model: str = "gpt-4o-mini"):
        if not MARKITDOWN_AVAILABLE:
            raise ImportError(
                "markitdown is not installed. Run: pip install 'markitdown[pdf,docx,pptx,xlsx]'"
            )
        self.llm_client = llm_client
        self.llm_model = llm_model

    def supported_extensions(self) -> list[str]:
        return ALL_EXTENSIONS

    def load(self, file_path: Path, **kwargs) -> list[LoadedDocument]:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        llm_client = kwargs.get("llm_client", self.llm_client)
        llm_model = kwargs.get("llm_model", self.llm_model)
        chunk = kwargs.get("chunk", True)
        ext = file_path.suffix.lower()

        md_kwargs = {}
        if ext in _IMAGE_EXTENSIONS and llm_client is not None:
            md_kwargs["llm_client"] = llm_client
            md_kwargs["llm_model"] = llm_model
            logger.info("MarkItDown converting image %s with LLM vision", file_path.name)
        else:
            logger.info("MarkItDown converting %s (local)", file_path.name)

        md = MarkItDown(**md_kwargs)
        result = md.convert(str(file_path))
        full_text = result.text_content

        if not full_text.strip():
            logger.warning("MarkItDown produced empty output for: %s", file_path)
            return []

        if chunk:
            sections = _split_by_headings(full_text)
        else:
            sections = [full_text]

        return [
            LoadedDocument(
                content=section,
                source=str(file_path),
                format=ext.lstrip("."),
                metadata={
                    "title": file_path.stem,
                    "section_index": i,
                    "total_sections": len(sections),
                },
            )
            for i, section in enumerate(sections)
        ]

    def load_full(self, file_path: Path, **kwargs) -> str:
        """返回完整 Markdown 文本（不分块），供 LLM 合并使用。"""
        docs = self.load(file_path, chunk=False, **kwargs)
        if not docs:
            return ""
        return docs[0].content
