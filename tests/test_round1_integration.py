import pytest
from pathlib import Path

from reqradar.modules.project_memory import ProjectMemory
from reqradar.modules.user_memory import UserMemory
from reqradar.modules.memory_manager import AnalysisMemoryManager
from reqradar.modules.synonym_resolver import SynonymResolver
from reqradar.infrastructure.template_loader import TemplateLoader


def test_memory_manager_uses_project_and_user_memory(tmp_path):
    mm = AnalysisMemoryManager(
        project_id=42,
        user_id=7,
        project_storage_path=str(tmp_path / "memories"),
        user_storage_path=str(tmp_path / "user_memories"),
        memory_enabled=True,
    )
    mm.project_memory.update_overview("Integration test project")
    mm.project_memory.add_tech_stack("languages", ["Python"])
    mm.project_memory.add_module("core", "Core module")
    mm.project_memory.save()
    mm.user_memory.add_correction("配置", ["config_proj"])
    mm.user_memory.set_preference("default_depth", "deep")
    mm.user_memory.save()

    profile_text = mm.get_project_profile_text()
    assert "Integration test project" in profile_text
    assert "Python" in profile_text

    user_text = mm.get_user_memory_text()
    assert "配置" in user_text
    assert "config_proj" in user_text


def test_synonym_resolver_with_project_memory(tmp_path):
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path=str(tmp_path / "memories"),
        user_storage_path=str(tmp_path / "user_memories"),
        memory_enabled=True,
    )
    mm.project_memory.add_term("配置", "Configuration settings", domain="general")
    mm.project_memory.save()

    resolver = SynonymResolver()
    keywords, mapping_log = resolver.expand_keywords_with_synonyms(
        keywords=["配置", "认证"],
        project_mappings=[],
        global_mappings=[],
    )
    assert "配置" in keywords


def test_template_loader_loads_default():
    loader = TemplateLoader()
    defn = loader.load_definition(loader.get_default_template_path())
    assert len(defn.sections) >= 7

    required = [s for s in defn.sections if s.required]
    assert len(required) >= 6

    prompts = loader.build_section_prompts(defn)
    assert "requirement_understanding" in prompts
    assert "影响力分析" in prompts.get("impact_analysis", "") or "impact" in prompts.get("impact_analysis", "")


def test_memory_manager_disabled():
    mm = AnalysisMemoryManager(
        project_id=1,
        user_id=1,
        project_storage_path="/tmp/unused",
        user_storage_path="/tmp/unused",
        memory_enabled=False,
    )
    assert mm.project_memory is None
    assert mm.user_memory is None
    assert mm.get_project_profile_text() == ""
    assert mm.get_user_memory_text() == ""
