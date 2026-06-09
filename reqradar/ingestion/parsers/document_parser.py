"""文档解析器 — markitdown 封装，支持 PDF/DOCX/PPTX/XLSX/HTML/Markdown。

将各种格式文档转化为统一 Markdown 文本。
"""

from __future__ import annotations

from pathlib import Path

from reqradar.kernel.exceptions import IngestionException

# markitdown 按需导入（降低启动开销）
_markitdown_available: bool | None = None


def _ensure_markitdown() -> None:
    """惰性加载 markitdown，未安装时抛出友好错误。"""
    global _markitdown_available
    if _markitdown_available is not None:
        return

    try:
        from markitdown import MarkItDown  # noqa: F401

        _markitdown_available = True
    except ImportError as e:
        _markitdown_available = False
        raise IngestionException(
            "markitdown 未安装，文档解析不可用。"
            "请运行: pip install 'markitdown[pdf,docx,pptx,xlsx,html]'"
        ) from e


class DocumentParser:
    """markitdown 封装 — 文件路径/字节流 → Markdown 文本。"""

    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50MB

    def __init__(self) -> None:
        _ensure_markitdown()

    def parse_file(self, file_path: Path) -> str:
        """解析文件为 Markdown 文本。

        Args:
            file_path: 文件路径

        Returns:
            Markdown 文本

        Raises:
            IngestionException: 文件不存在、过大或解析失败
        """
        if not file_path.exists():
            raise IngestionException(
                f"文件不存在: {file_path}",
                detail={"file_path": str(file_path)},
            )

        file_size = file_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE_BYTES:
            raise IngestionException(
                f"文件过大: {file_size} bytes (最大 {self.MAX_FILE_SIZE_BYTES} bytes)",
                detail={"file_path": str(file_path), "file_size": file_size},
            )

        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(file_path)
            return result.text_content
        except Exception as e:
            raise IngestionException(
                f"文档解析失败: {file_path}",
                detail={"file_path": str(file_path), "error": str(e)},
            ) from e

    def parse_bytes(self, content: bytes, filename: str, suffix: str = ".tmp") -> str:
        """从字节流解析文档。

        Args:
            content: 文档字节内容
            filename: 文件名（用于推断格式）
            suffix: 临时文件后缀

        Returns:
            Markdown 文本
        """
        import tempfile

        if len(content) > self.MAX_FILE_SIZE_BYTES:
            raise IngestionException(
                f"文件过大: {len(content)} bytes (最大 {self.MAX_FILE_SIZE_BYTES} bytes)",
                detail={"filename": filename, "file_size": len(content)},
            )

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)

            return self.parse_file(tmp_path)
        finally:
            if "tmp_path" in locals():
                tmp_path.unlink(missing_ok=True)
