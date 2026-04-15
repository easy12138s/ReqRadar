"""文档加载器模块"""

from reqradar.modules.loaders.base import DocumentLoader, LoadedDocument, LoaderRegistry, get_loader

__all__ = [
    "DocumentLoader",
    "LoadedDocument",
    "LoaderRegistry",
    "get_loader",
    "TextLoader",
    "ImageLoader",
    "ChatLoader",
]

from reqradar.modules.loaders.chat_loader import ChatLoader  # noqa: E402
from reqradar.modules.loaders.image_loader import ImageLoader  # noqa: E402
from reqradar.modules.loaders.text_loader import TextLoader  # noqa: E402

LoaderRegistry.register("text", TextLoader())
LoaderRegistry.register("image", ImageLoader())
LoaderRegistry.register("chat", ChatLoader())

try:
    from reqradar.modules.loaders.pdf_loader import PDFLoader  # noqa: F401

    LoaderRegistry.register("pdf", PDFLoader())
except ImportError:
    pass

try:
    from reqradar.modules.loaders.docx_loader import DocxLoader  # noqa: F401

    LoaderRegistry.register("docx", DocxLoader())
except ImportError:
    pass
