"""文档加载器基类与注册表"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from reqradar.core.exceptions import LoaderException


@dataclass
class LoadedDocument:
    content: str
    source: str
    format: str
    metadata: dict = field(default_factory=dict)
    images: list[bytes] = field(default_factory=list)


class DocumentLoader(ABC):
    """文档加载器抽象基类"""

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """返回支持的文件扩展名列表"""

    @abstractmethod
    def load(self, file_path: Path, **kwargs) -> list[LoadedDocument]:
        """加载文档，返回分块后的文档列表"""

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions()


class LoaderRegistry:
    """加载器注册表"""

    _loaders: dict[str, DocumentLoader] = {}

    @classmethod
    def register(cls, name: str, loader: DocumentLoader):
        cls._loaders[name] = loader

    @classmethod
    def get(cls, name: str) -> DocumentLoader:
        if name not in cls._loaders:
            raise LoaderException(f"Unknown loader: {name}")
        return cls._loaders[name]

    @classmethod
    def get_for_file(cls, file_path: Path) -> Optional[DocumentLoader]:
        for loader in cls._loaders.values():
            if loader.supports(file_path):
                return loader
        return None

    @classmethod
    def list_available(cls) -> list[str]:
        return list(cls._loaders.keys())


def register_loader(name: str):
    """装饰器：注册加载器"""

    def decorator(cls):
        LoaderRegistry.register(name, cls())
        return cls

    return decorator


def get_loader(file_path: Path) -> Optional[DocumentLoader]:
    """根据文件路径获取合适的加载器"""
    return LoaderRegistry.get_for_file(file_path)
