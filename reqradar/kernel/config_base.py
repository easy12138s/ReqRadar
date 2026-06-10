"""Scope×Domain 配置基类 — 三级配置解析链。

配置优先级：用户级 > 项目级 > 系统级 > 默认值。
每个配置项属于一个 Domain（业务域），通过 Scope（作用域）决定覆盖层次。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from reqradar.kernel.types import Domain, Scope


@dataclass
class ScopeDomainConfig:
    """单条配置项，绑定到特定的 Scope 和 Domain。"""

    scope: Scope
    domain: Domain
    key: str
    value: Any
    value_type: str = "string"
    description: str = ""


@dataclass
class ConfigResolutionChain:
    """配置解析链 — 按优先级从高到低解析配置值。

    解析顺序：USER → PROJECT → GLOBAL → 默认值。

    使用方式：
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        chain.add(ScopeDomainConfig(Scope.PROJECT, Domain.SESSION, "max_steps", 30))
        result = chain.resolve(Domain.SESSION, "max_steps")  # 返回 30
    """

    _entries: list[ScopeDomainConfig] = field(default_factory=list)
    _defaults: dict[str, Any] = field(default_factory=dict)

    _SCOPE_PRIORITY: dict[Scope, int] = field(
        default_factory=lambda: {Scope.SESSION: 4, Scope.USER: 3, Scope.PROJECT: 2, Scope.GLOBAL: 1}
    )

    def add(self, config: ScopeDomainConfig) -> None:
        """添加一条配置项到解析链。

        Args:
            config: 配置项
        """
        self._entries.append(config)

    def set_default(self, domain_key: str, value: Any) -> None:
        """设置默认值（最低优先级）。

        Args:
            domain_key: 格式为 "domain.key"，如 "session.max_steps"
            value: 默认值
        """
        self._defaults[domain_key] = value

    def resolve(self, domain: Domain, key: str, scope_hint: Scope | None = None) -> Any:
        """按优先级解析配置值。

        Args:
            domain: 配置业务域
            key: 配置键
            scope_hint: 可选的作用域提示，限制搜索范围

        Returns:
            解析到的配置值，未找到返回 None
        """
        matches = [
            e
            for e in self._entries
            if e.domain == domain and e.key == key and (scope_hint is None or e.scope == scope_hint)
        ]

        if not matches:
            return self._defaults.get(f"{domain.value}.{key}")

        matches.sort(key=lambda e: self._SCOPE_PRIORITY.get(e.scope, 0), reverse=True)
        return matches[0].value

    def resolve_all(self, domain: Domain, key: str) -> list[ScopeDomainConfig]:
        """返回指定配置项在所有作用域中的值。

        Args:
            domain: 配置业务域
            key: 配置键

        Returns:
            所有匹配的配置项列表，按优先级从高到低排序
        """
        matches = [e for e in self._entries if e.domain == domain and e.key == key]
        matches.sort(key=lambda e: self._SCOPE_PRIORITY.get(e.scope, 0), reverse=True)
        return matches

    def list_by_domain(self, domain: Domain) -> list[ScopeDomainConfig]:
        """列出指定业务域下的所有配置项。

        Args:
            domain: 配置业务域

        Returns:
            该域下的所有配置项
        """
        return [e for e in self._entries if e.domain == domain]


@dataclass
class ConfigMatrixBase:
    """Scope×Domain 配置矩阵基类。

    管理所有配置项的注册、查询和验证。
    各服务通过继承此类扩展特定的配置管理逻辑。
    """

    chain: ConfigResolutionChain = field(default_factory=ConfigResolutionChain)
    _schema_registry: dict[str, dict[str, type]] = field(default_factory=dict)

    def register_schema(self, domain: Domain, schema: dict[str, type]) -> None:
        """注册配置域的 Schema（键→类型映射）。

        Args:
            domain: 配置业务域
            schema: 配置键到类型的映射，如 {"max_steps": int, "enabled": bool}
        """
        self._schema_registry[domain.value] = schema

    def get_schema(self, domain: Domain) -> dict[str, type] | None:
        """获取配置域的 Schema。

        Args:
            domain: 配置业务域

        Returns:
            配置键到类型的映射，未注册返回 None
        """
        return self._schema_registry.get(domain.value)

    def validate_value(self, domain: Domain, key: str, value: Any) -> bool:
        """验证配置值是否符合 Schema。

        Args:
            domain: 配置业务域
            key: 配置键
            value: 待验证的值

        Returns:
            验证通过返回 True，否则返回 False
        """
        schema = self.get_schema(domain)
        if schema is None or key not in schema:
            return True
        expected_type = schema[key]
        try:
            if expected_type is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "false", "1", "0")
                return isinstance(value, bool)
            if expected_type is int:
                if isinstance(value, str):
                    int(value)
                    return True
                return isinstance(value, int) and not isinstance(value, bool)
            if expected_type is float:
                if isinstance(value, str):
                    float(value)
                    return True
                return isinstance(value, int | float)
            return isinstance(value, str)
        except (ValueError, TypeError):
            return False

    def resolve(self, domain: Domain, key: str, scope_hint: Scope | None = None) -> Any:
        """解析配置值（代理到内部解析链）。

        Args:
            domain: 配置业务域
            key: 配置键
            scope_hint: 可选的作用域提示

        Returns:
            解析到的配置值
        """
        return self.chain.resolve(domain, key, scope_hint)
