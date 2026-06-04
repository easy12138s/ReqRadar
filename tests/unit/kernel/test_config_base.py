"""Kernel Scope×Domain 配置基类的单元测试。"""

from reqradar.kernel.config_base import (
    ConfigMatrixBase,
    ConfigResolutionChain,
    ScopeDomainConfig,
)
from reqradar.kernel.types import Domain, Scope


class TestScopeDomainConfig:
    def test_creation_with_defaults(self):
        config = ScopeDomainConfig(
            scope=Scope.GLOBAL, domain=Domain.SESSION, key="max_steps", value=50
        )
        assert config.scope == Scope.GLOBAL
        assert config.domain == Domain.SESSION
        assert config.key == "max_steps"
        assert config.value == 50
        assert config.value_type == "string"
        assert config.description == ""


class TestConfigResolutionChain:
    def test_resolve_returns_none_when_empty(self):
        chain = ConfigResolutionChain()
        assert chain.resolve(Domain.SESSION, "max_steps") is None

    def test_resolve_single_global_value(self):
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        assert chain.resolve(Domain.SESSION, "max_steps") == 50

    def test_project_overrides_global(self):
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        chain.add(ScopeDomainConfig(Scope.PROJECT, Domain.SESSION, "max_steps", 30))
        assert chain.resolve(Domain.SESSION, "max_steps") == 30

    def test_user_overrides_project(self):
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        chain.add(ScopeDomainConfig(Scope.PROJECT, Domain.SESSION, "max_steps", 30))
        chain.add(ScopeDomainConfig(Scope.USER, Domain.SESSION, "max_steps", 10))
        assert chain.resolve(Domain.SESSION, "max_steps") == 10

    def test_resolve_returns_default_when_no_entries(self):
        chain = ConfigResolutionChain()
        chain.set_default("session.max_steps", 100)
        assert chain.resolve(Domain.SESSION, "max_steps") == 100

    def test_entry_overrides_default(self):
        chain = ConfigResolutionChain()
        chain.set_default("session.max_steps", 100)
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        assert chain.resolve(Domain.SESSION, "max_steps") == 50

    def test_different_domains_independent(self):
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        assert chain.resolve(Domain.EVENT, "max_steps") is None

    def test_different_keys_independent(self):
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        assert chain.resolve(Domain.SESSION, "timeout") is None

    def test_resolve_with_scope_hint(self):
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        chain.add(ScopeDomainConfig(Scope.PROJECT, Domain.SESSION, "max_steps", 30))
        assert chain.resolve(Domain.SESSION, "max_steps", scope_hint=Scope.GLOBAL) == 50

    def test_resolve_all_returns_all_scopes(self):
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        chain.add(ScopeDomainConfig(Scope.PROJECT, Domain.SESSION, "max_steps", 30))
        results = chain.resolve_all(Domain.SESSION, "max_steps")
        assert len(results) == 2
        assert results[0].scope == Scope.PROJECT
        assert results[1].scope == Scope.GLOBAL

    def test_list_by_domain(self):
        chain = ConfigResolutionChain()
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "a", 1))
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "b", 2))
        chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.EVENT, "c", 3))
        session_configs = chain.list_by_domain(Domain.SESSION)
        assert len(session_configs) == 2


class TestConfigMatrixBase:
    def test_register_and_get_schema(self):
        matrix = ConfigMatrixBase()
        matrix.register_schema(Domain.SESSION, {"max_steps": int, "enabled": bool})
        schema = matrix.get_schema(Domain.SESSION)
        assert schema == {"max_steps": int, "enabled": bool}

    def test_get_schema_returns_none_for_unregistered(self):
        matrix = ConfigMatrixBase()
        assert matrix.get_schema(Domain.EVENT) is None

    def test_validate_int_value_from_string(self):
        matrix = ConfigMatrixBase()
        matrix.register_schema(Domain.SESSION, {"max_steps": int})
        assert matrix.validate_value(Domain.SESSION, "max_steps", "50") is True
        assert matrix.validate_value(Domain.SESSION, "max_steps", "abc") is False

    def test_validate_bool_value_from_string(self):
        matrix = ConfigMatrixBase()
        matrix.register_schema(Domain.SESSION, {"enabled": bool})
        assert matrix.validate_value(Domain.SESSION, "enabled", "true") is True
        assert matrix.validate_value(Domain.SESSION, "enabled", "false") is True
        assert matrix.validate_value(Domain.SESSION, "enabled", "maybe") is False

    def test_validate_float_value(self):
        matrix = ConfigMatrixBase()
        matrix.register_schema(Domain.L3, {"decay_rate": float})
        assert matrix.validate_value(Domain.L3, "decay_rate", "0.05") is True
        assert matrix.validate_value(Domain.L3, "decay_rate", "abc") is False

    def test_validate_unknown_key_returns_true(self):
        matrix = ConfigMatrixBase()
        matrix.register_schema(Domain.SESSION, {"max_steps": int})
        assert matrix.validate_value(Domain.SESSION, "unknown_key", "anything") is True

    def test_resolve_delegates_to_chain(self):
        matrix = ConfigMatrixBase()
        matrix.chain.add(ScopeDomainConfig(Scope.GLOBAL, Domain.SESSION, "max_steps", 50))
        assert matrix.resolve(Domain.SESSION, "max_steps") == 50
