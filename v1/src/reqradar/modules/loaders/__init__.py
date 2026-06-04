"""文档加载器模块"""

from reqradar.modules.loaders.base import DocumentLoader, LoadedDocument, LoaderRegistry, get_loader

__all__ = [
    "DocumentLoader",
    "LoadedDocument",
    "LoaderRegistry",
    "get_loader",
    "MarkitdownLoader",
    "TextLoader",
    "ChatLoader",
]

from reqradar.modules.loaders.chat_loader import ChatLoader  # noqa: E402
from reqradar.modules.loaders.text_loader import TextLoader  # noqa: E402

LoaderRegistry.register("chat", ChatLoader())
LoaderRegistry.register("text", TextLoader())

try:
    from reqradar.modules.loaders.markitdown_loader import MarkitdownLoader  # noqa: F401

    LoaderRegistry.register("markitdown", MarkitdownLoader())
except ImportError:
    pass
