"""MCP 数据模型单元测试"""

import pytest

from reqradar.mcp.schemas import (
    ProjectMemoryOutput,
    RequirementDetail,
    RequirementSummary,
    SearchRequirementsInput,
)


class TestSearchRequirementsInput:
    def test_defaults(self):
        inp = SearchRequirementsInput()
        assert inp.project_id is None
        assert inp.query is None
        assert inp.limit == 10

    def test_custom_values(self):
        inp = SearchRequirementsInput(project_id=5, query="test", limit=20)
        assert inp.project_id == 5
        assert inp.query == "test"
        assert inp.limit == 20

    def test_limit_validation_min(self):
        with pytest.raises(Exception):
            SearchRequirementsInput(limit=0)

    def test_limit_validation_max(self):
        with pytest.raises(Exception):
            SearchRequirementsInput(limit=100)

    def test_valid_boundary_values(self):
        inp_min = SearchRequirementsInput(limit=1)
        assert inp_min.limit == 1
        inp_max = SearchRequirementsInput(limit=50)
        assert inp_max.limit == 50


class TestRequirementSummary:
    def test_creation(self):
        summary = RequirementSummary(
            id=1,
            project_id=10,
            release_code="REQ-001",
            version=2,
            title="Test",
            content="Content here",
            published_at="2026-01-01T00:00:00Z",
        )
        assert summary.id == 1
        assert summary.release_code == "REQ-001"

    def test_optional_published_at(self):
        summary = RequirementSummary(
            id=1,
            project_id=10,
            release_code="REQ-002",
            version=1,
            title="Test",
            content="Content",
            published_at=None,
        )
        assert summary.published_at is None


class TestRequirementDetail:
    def test_creation_with_context_json(self):
        detail = RequirementDetail(
            id=1,
            release_code="REQ-003",
            version=3,
            title="Detail Test",
            content="Full content",
            context_json={"tech_stack": ["Python", "FastAPI"]},
        )
        assert detail.context_json["tech_stack"] == ["Python", "FastAPI"]

    def test_empty_context_json(self):
        detail = RequirementDetail(
            id=2,
            release_code="REQ-004",
            version=1,
            title="Empty Context",
            content="No context",
            context_json={},
        )
        assert detail.context_json == {}


class TestProjectMemoryOutput:
    def test_creation_with_memory(self):
        output = ProjectMemoryOutput(project_id=5, memory={"terminology": {"API": "Application Interface"}})
        assert output.project_id == 5
        assert output.memory is not None

    def test_creation_without_memory(self):
        output = ProjectMemoryOutput(project_id=6, memory=None)
        assert output.project_id == 6
        assert output.memory is None
