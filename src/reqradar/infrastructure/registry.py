"""插件注册表 - 模块可扩展性支持"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Type


@dataclass
class RegisteredPlugin:
    name: str
    cls: Type
    factory: Optional[Callable] = None


class Registry:
    """通用注册表基类"""

    _registry: Dict[str, RegisteredPlugin] = {}
    _default: Optional[str] = None

    @classmethod
    def register(cls, name: str, default: bool = False):
        """注册装饰器"""

        def decorator(plugin_cls: Type):
            cls._registry[name] = RegisteredPlugin(name=name, cls=plugin_cls)
            if default or len(cls._registry) == 1:
                cls._default = name
            return plugin_cls

        return decorator

    @classmethod
    def get(cls, name: Optional[str] = None) -> Type:
        """获取注册的类"""
        if name is None:
            name = cls._default
        if name not in cls._registry:
            raise ValueError(f"Unknown {cls.__name__} implementation: {name}")
        return cls._registry[name].cls

    @classmethod
    def list_available(cls) -> list[str]:
        """列出所有可用的实现"""
        return list(cls._registry.keys())

    @classmethod
    def get_default(cls) -> Optional[str]:
        return cls._default
