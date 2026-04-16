"""测试记忆系统与步骤的集成"""

from pathlib import Path

import pytest

from reqradar.agent.steps import EXTRACT_PROMPT
from reqradar.core.context import AnalysisContext, RequirementUnderstanding
from reqradar.modules.memory import MemoryManager


class TestMemoryInjection:
    def test_step_extract_includes_terminology_in_prompt(self, tmp_path):
        context = AnalysisContext(
            requirement_path=Path("test.md"),
            memory_data={
                "terminology": [
                    {"term": "SSO", "definition": "统一身份认证", "context": ""},
                    {"term": "RBAC", "definition": "基于角色的访问控制", "context": "权限模块"},
                ],
                "team": [],
                "analysis_history": [],
            },
        )
        context.requirement_text = "测试需求文档"

        terminology_section = ""
        if context.memory_data and context.memory_data.get("terminology"):
            terms = context.memory_data["terminology"]
            if terms:
                lines = ["项目已知术语（请优先识别这些术语）："]
                for t in terms:
                    line = f"- {t['term']}"
                    if t.get("definition"):
                        line += f": {t['definition']}"
                    lines.append(line)
                terminology_section = "\n".join(lines)

        prompt = EXTRACT_PROMPT.format(
            content=context.requirement_text,
            terminology_section=terminology_section,
            project_context_section="",
        )

        assert "SSO" in prompt
        assert "RBAC" in prompt
        assert "项目已知术语" in prompt

    def test_step_extract_without_memory(self, tmp_path):
        context = AnalysisContext(requirement_path=Path("test.md"))
        context.requirement_text = "测试需求文档"

        terminology_section = ""
        if context.memory_data and context.memory_data.get("terminology"):
            terms = context.memory_data["terminology"]
            if terms:
                lines = ["项目已知术语（请优先识别这些术语）："]
                for t in terms:
                    lines.append(f"- {t['term']}")
                terminology_section = "\n".join(lines)

        prompt = EXTRACT_PROMPT.format(
            content=context.requirement_text,
            terminology_section=terminology_section,
            project_context_section="",
        )

        assert "项目已知术语" not in prompt

    def test_memory_persistence_roundtrip(self, tmp_path):
        manager = MemoryManager(storage_path=str(tmp_path / "memory"))
        manager.add_term("API", "Application Programming Interface")
        manager.add_team_member("Alice", "Tech Lead", ["api", "auth"])
        manager.add_analysis_record("test-req", "Test findings", "low")

        manager2 = MemoryManager(storage_path=str(tmp_path / "memory"))
        data = manager2.load()
        assert len(data["terminology"]) == 1
        assert data["terminology"][0]["term"] == "API"
        assert len(data["team"]) == 1
        assert len(data["analysis_history"]) == 1


class TestContextWithMemory:
    def test_context_stores_memory_data(self):
        context = AnalysisContext(
            requirement_path=Path("test.md"),
            memory_data={"terminology": [], "team": [], "analysis_history": []},
        )
        assert context.memory_data is not None
        assert "terminology" in context.memory_data

    def test_context_without_memory(self):
        context = AnalysisContext(requirement_path=Path("test.md"))
        assert context.memory_data is None
