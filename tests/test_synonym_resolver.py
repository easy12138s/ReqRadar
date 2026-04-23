import pytest

from reqradar.modules.synonym_resolver import SynonymResolver


def test_resolve_with_project_mappings():
    resolver = SynonymResolver()
    project_mappings = [
        {"business_term": "配置", "code_terms": ["config", "settings"], "priority": 100},
        {"business_term": "用户", "code_terms": ["user", "account"], "priority": 50},
    ]
    global_mappings = [
        {"business_term": "认证", "code_terms": ["auth", "login"], "priority": 100},
    ]

    result = resolver.resolve(["配置", "用户", "认证"], project_mappings, global_mappings)
    assert "config" in result or "settings" in result
    assert "user" in result or "account" in result
    assert "auth" in result or "login" in result


def test_project_mappings_override_global():
    resolver = SynonymResolver()
    project_mappings = [
        {"business_term": "配置", "code_terms": ["config_proj"], "priority": 50},
    ]
    global_mappings = [
        {"business_term": "配置", "code_terms": ["config_global"], "priority": 200},
    ]

    result = resolver.resolve(["配置"], project_mappings, global_mappings)
    assert "config_proj" in result
    assert "config_global" not in result


def test_resolve_empty_keywords():
    resolver = SynonymResolver()
    result = resolver.resolve([], [], [])
    assert result == []


def test_fallback_to_hardcoded():
    resolver = SynonymResolver()
    result = resolver.resolve(["配置"], [], [])
    assert len(result) > 0


def test_priority_sorting():
    resolver = SynonymResolver()
    project_mappings = [
        {"business_term": "配置", "code_terms": ["high_priority_term"], "priority": 1},
        {"business_term": "配置", "code_terms": ["low_priority_term"], "priority": 200},
    ]
    global_mappings = []

    result = resolver.resolve(["配置"], project_mappings, global_mappings)
    assert "high_priority_term" in result or "low_priority_term" in result
