import pytest

from reqradar.web.models import (
    PendingChange,
    SynonymMapping,
    ReportTemplate,
    AnalysisTask,
    Project,
)


def test_pending_change_model_fields():
    change = PendingChange(
        project_id=1,
        change_type="profile",
        target_id="module:auth",
        old_value="",
        new_value="### auth\nAuthentication module",
        diff="+ ### auth\n+ Authentication module",
        source="agent",
        status="pending",
    )
    assert change.project_id == 1
    assert change.change_type == "profile"
    assert change.status == "pending"


def test_synonym_mapping_model_fields():
    mapping = SynonymMapping(
        project_id=1,
        business_term="配置",
        code_terms='["config", "settings"]',
        priority=100,
        source="user",
    )
    assert mapping.business_term == "配置"
    assert mapping.priority == 100


def test_report_template_model_fields():
    template = ReportTemplate(
        name="Default Template",
        definition="sections: []",
        render_template="# {{ title }}",
        is_default=True,
    )
    assert template.is_default is True
    assert template.name == "Default Template"


def test_analysis_task_new_fields():
    task = AnalysisTask(
        project_id=1,
        user_id=1,
        requirement_name="test",
        requirement_text="test text",
        current_version=1,
        depth="standard",
    )
    assert task.current_version == 1
    assert task.depth == "standard"


def test_project_model_has_source_fields():
    columns = {c.name for c in Project.__table__.columns}
    assert "source_type" in columns
    assert "source_url" in columns


def test_project_model_no_old_path_fields():
    columns = {c.name for c in Project.__table__.columns}
    assert "repo_path" not in columns
    assert "docs_path" not in columns
    assert "index_path" not in columns
    assert "config_json" not in columns
