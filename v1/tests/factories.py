from datetime import UTC, datetime
from itertools import count

from reqradar.web.api.auth import hash_password
from reqradar.web.enums import TaskStatus
from reqradar.web.models import (
    AnalysisTask,
    MCPAccessKey,
    PendingChange,
    Project,
    Report,
    ReportTemplate,
    ReportVersion,
    RequirementDocument,
    RequirementRelease,
    SynonymMapping,
    User,
)

_seq = count(1)


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}{next(_seq)}@example.com"


def build_user(**overrides) -> User:
    index = next(_seq)
    data = {
        "email": f"user{index}@example.com",
        "password_hash": hash_password("Password123"),
        "display_name": f"User {index}",
        "role": "user",
    }
    data.update(overrides)
    return User(**data)


def build_project(owner_id: int, **overrides) -> Project:
    index = next(_seq)
    data = {
        "name": f"project_{index}",
        "description": "Sample project",
        "source_type": "local",
        "source_url": "",
        "owner_id": owner_id,
    }
    data.update(overrides)
    return Project(**data)


def build_requirement_document(project_id: int, user_id: int, **overrides) -> RequirementDocument:
    index = next(_seq)
    data = {
        "project_id": project_id,
        "user_id": user_id,
        "title": f"Requirement {index}",
        "consolidated_text": "用户需要导入需求并生成分析报告",
        "source_files": [{"filename": "requirement.md", "size": 32}],
        "status": "ready",
        "version": 1,
    }
    data.update(overrides)
    return RequirementDocument(**data)


def build_analysis_task(project_id: int, user_id: int, **overrides) -> AnalysisTask:
    index = next(_seq)
    data = {
        "project_id": project_id,
        "user_id": user_id,
        "requirement_name": f"Requirement {index}",
        "requirement_text": "As a user, I want the system to analyze requirements.",
        "status": TaskStatus.PENDING,
        "context_json": {},
        "depth": "standard",
    }
    data.update(overrides)
    return AnalysisTask(**data)


def build_report(task_id: int, **overrides) -> Report:
    data = {
        "task_id": task_id,
        "content_markdown": "# Report\n\n分析结果",
        "content_html": "<h1>Report</h1><p>分析结果</p>",
        "markdown_path": "",
        "html_path": "",
    }
    data.update(overrides)
    return Report(**data)


def build_report_version(task_id: int, created_by: int, **overrides) -> ReportVersion:
    data = {
        "task_id": task_id,
        "version_number": 1,
        "report_data": {"summary": "ok"},
        "context_snapshot": {"created_at": datetime.now(UTC).isoformat()},
        "content_markdown": "# Version 1",
        "content_html": "<h1>Version 1</h1>",
        "trigger_type": "initial",
        "trigger_description": "Initial report",
        "created_by": created_by,
    }
    data.update(overrides)
    return ReportVersion(**data)


def build_report_template(**overrides) -> ReportTemplate:
    index = next(_seq)
    data = {
        "name": f"Template {index}",
        "description": "Test template",
        "definition": "{}",
        "render_template": "# {{ title }}",
        "is_default": False,
        "created_by": None,
    }
    data.update(overrides)
    return ReportTemplate(**data)


def build_requirement_release(project_id: int, user_id: int, **overrides) -> RequirementRelease:
    index = next(_seq)
    data = {
        "project_id": project_id,
        "user_id": user_id,
        "release_code": f"REL-{index:03d}",
        "version": 1,
        "title": f"Release {index}",
        "content": "需求文档内容",
        "context_json": {},
        "status": "draft",
    }
    data.update(overrides)
    return RequirementRelease(**data)


def build_synonym(**overrides) -> SynonymMapping:
    index = next(_seq)
    data = {
        "project_id": None,
        "business_term": f"业务术语{index}",
        "code_terms": [f"code_term_{index}"],
        "priority": 100,
        "source": "user",
    }
    data.update(overrides)
    return SynonymMapping(**data)


def build_pending_change(project_id: int, **overrides) -> PendingChange:
    index = next(_seq)
    data = {
        "project_id": project_id,
        "change_type": "update",
        "target_id": f"target-{index}",
        "old_value": "旧值",
        "new_value": "新值",
        "diff": "-旧值\n+新值",
        "source": "analysis",
        "status": "pending",
    }
    data.update(overrides)
    return PendingChange(**data)


def build_mcp_access_key(user_id: int, **overrides) -> MCPAccessKey:
    index = next(_seq)
    data = {
        "user_id": user_id,
        "key_prefix": f"mcp_{index:06d}"[:12],
        "key_hash": f"hashed_key_{index}",
        "name": f"Test Key {index}",
        "scopes": ["read"],
        "is_active": True,
    }
    data.update(overrides)
    return MCPAccessKey(**data)
