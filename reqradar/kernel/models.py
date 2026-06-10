"""ORM 模型定义 — V1 搬迁 + V2 新增，SQLAlchemy 声明式映射。

V1 搬迁表（19 张）：
  users, revoked_tokens, user_configs, system_configs, projects, project_configs,
  requirement_documents, analysis_tasks, reports, uploaded_files, pending_changes,
  synonym_mappings, report_templates, report_versions, report_chats,
  llm_call_logs, mcp_access_keys, requirement_releases, mcp_tool_calls

V2 新增核心表（6 张，Batch 3）：
  cognitive_sessions, events, checkpoints,
  evidence_records, evidence_relations, dimension_results
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reqradar.kernel.database import Base
from reqradar.kernel.enums import (
    ChangeStatus,
    DimensionStatus,
    EvidenceStatus,
    FreshnessStatus,
    ReleaseStatus,
    SessionStatus,
    TaskStatus,
)


def utc_now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# 基础表（Batch 1 — V1 搬迁 + C-06 DDL 适配）
# ---------------------------------------------------------------------------


class User(Base):
    """用户表 — V1 搬迁，V2 适配 UUID 主键。"""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    projects: Mapped[list[Project]] = relationship(back_populates="owner")
    analysis_tasks: Mapped[list[AnalysisTask]] = relationship(back_populates="user")
    configs: Mapped[list[UserConfig]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Project(Base):
    """项目表 — V1 搬迁，V2 适配 UUID 主键。"""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="creating", nullable=False)
    profile_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    default_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_templates.id"), nullable=True
    )

    owner: Mapped[User | None] = relationship(back_populates="projects")
    analysis_tasks: Mapped[list[AnalysisTask]] = relationship(back_populates="project")
    configs: Mapped[list[ProjectConfig]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    default_template: Mapped[ReportTemplate | None] = relationship()
    raw_contexts: Mapped[list[RawContext]] = relationship(
        "RawContext", back_populates="project", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[Chunk]] = relationship(
        "Chunk", back_populates="project", cascade="all, delete-orphan"
    )
    code_modules_list: Mapped[list[CodeModule]] = relationship(
        "CodeModule", back_populates="project", cascade="all, delete-orphan"
    )
    git_commits: Mapped[list[GitCommit]] = relationship(
        "GitCommit", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("name", "owner_id", name="uq_project_name_owner"),)


class RevokedToken(Base):
    """JWT 吊销表。"""

    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class UserConfig(Base):
    """用户配置表。"""

    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), server_default="string", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="configs")

    __table_args__ = (UniqueConstraint("user_id", "config_key", name="uq_user_configs_user_key"),)


class SystemConfig(Base):
    """系统配置表。"""

    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), server_default="string", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class ProjectConfig(Base):
    """项目配置表。"""

    __tablename__ = "project_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), server_default="string", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="configs")

    __table_args__ = (
        UniqueConstraint("project_id", "config_key", name="uq_project_configs_project_key"),
    )


class ReportTemplate(Base):
    """报告模板表。"""

    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    render_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


# ---------------------------------------------------------------------------
# V1 业务表（搬迁保留，适配 UUID 外键）
# ---------------------------------------------------------------------------


class RequirementDocument(Base):
    """需求文档表。"""

    __tablename__ = "requirement_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), server_default="", nullable=False)
    consolidated_text: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    source_files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), server_default="ready", nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    project: Mapped[Project] = relationship(backref="requirement_documents")
    user: Mapped[User] = relationship(backref="requirement_documents")


class AnalysisTask(Base):
    """分析任务表。"""

    __tablename__ = "analysis_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    requirement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_documents.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), server_default=TaskStatus.PENDING, nullable=False
    )
    context_json: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    depth: Mapped[str] = mapped_column(String(20), server_default="standard", nullable=False)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_templates.id"), nullable=True
    )
    focus_areas: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    progress_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project: Mapped[Project] = relationship(back_populates="analysis_tasks")
    user: Mapped[User] = relationship(back_populates="analysis_tasks")
    requirement_document: Mapped[RequirementDocument | None] = relationship(
        backref="analysis_tasks"
    )
    report: Mapped[Report | None] = relationship(back_populates="task", uselist=False)
    uploaded_files: Mapped[list[UploadedFile]] = relationship(back_populates="task")
    versions: Mapped[list[ReportVersion]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    chats: Mapped[list[ReportChat]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class Report(Base):
    """分析报告表。"""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_tasks.id"), unique=True, nullable=False
    )
    content_markdown: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    content_html: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    markdown_path: Mapped[str] = mapped_column(String(512), server_default="", nullable=False)
    html_path: Mapped[str] = mapped_column(String(512), server_default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    task: Mapped[AnalysisTask] = relationship(back_populates="report")


class UploadedFile(Base):
    """上传文件记录表。"""

    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    task: Mapped[AnalysisTask] = relationship(back_populates="uploaded_files")


class PendingChange(Base):
    """待审核变更表。"""

    __tablename__ = "pending_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    new_value: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    diff: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default=ChangeStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class SynonymMapping(Base):
    """术语同义词映射表。"""

    __tablename__ = "synonym_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    business_term: Mapped[str] = mapped_column(String(200), nullable=False)
    code_terms: Mapped[list] = mapped_column(JSON, server_default="[]", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, server_default="100", nullable=False)
    source: Mapped[str] = mapped_column(String(50), server_default="user", nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "business_term", name="uq_synonym_project_term"),
    )


class ReportVersion(Base):
    """报告版本表。"""

    __tablename__ = "report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    report_data: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    content_html: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    markdown_path: Mapped[str] = mapped_column(String(512), server_default="", nullable=False)
    html_path: Mapped[str] = mapped_column(String(512), server_default="", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), server_default="initial", nullable=False)
    trigger_description: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    task: Mapped[AnalysisTask] = relationship(back_populates="versions")
    creator: Mapped[User] = relationship()


class ReportChat(Base):
    """报告对话记录表。"""

    __tablename__ = "report_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, server_default="[]", nullable=False)
    intent_type: Mapped[str] = mapped_column(String(50), server_default="other", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    task: Mapped[AnalysisTask] = relationship(back_populates="chats")


class LLMCallLog(Base):
    """LLM 调用日志表。"""

    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_tasks.id"), nullable=True)
    caller: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    completion_chars: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    tool_calls_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    tool_names: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class MCPAccessKey(Base):
    """MCP 访问密钥表。"""

    __tablename__ = "mcp_access_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), server_default="", nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, server_default="[]", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    user: Mapped[User] = relationship()


class RequirementRelease(Base):
    """需求发布版本表。"""

    __tablename__ = "requirement_releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_tasks.id"), nullable=True)
    release_code: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    title: Mapped[str] = mapped_column(String(255), server_default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    context_json: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default=ReleaseStatus.DRAFT, nullable=False
    )
    superseded_by: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_releases.id"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    project: Mapped[Project] = relationship()
    user: Mapped[User] = relationship()
    task: Mapped[AnalysisTask | None] = relationship()
    superseder: Mapped[RequirementRelease | None] = relationship(
        remote_side=[id], foreign_keys=[superseded_by]
    )

    __table_args__ = (
        UniqueConstraint("release_code", "version", name="uq_requirement_release_code_version"),
    )


class MCPToolCall(Base):
    """MCP 工具调用审计表。"""

    __tablename__ = "mcp_tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    access_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("mcp_access_keys.id"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    arguments_json: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    result_summary: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    access_key: Mapped[MCPAccessKey | None] = relationship()


# ---------------------------------------------------------------------------
# V2 新增核心表（Batch 3 — L2 认知层）
# ---------------------------------------------------------------------------


class CognitiveSession(Base):
    """认知会话表 — V2 Runtime 核心实体。"""

    __tablename__ = "cognitive_sessions"

    session_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default=SessionStatus.CREATED.value, nullable=False
    )
    config: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    state: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_checkpoint_version: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    total_reasoning_steps: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    total_tool_calls: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    status_history: Mapped[list] = mapped_column(JSON, server_default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship()
    user: Mapped[User] = relationship()
    events: Mapped[list[Event]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    checkpoints: Mapped[list[Checkpoint]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    evidence_records: Mapped[list[EvidenceRecord]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    dimension_results: Mapped[list[DimensionResult]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Event(Base):
    """事件流表 — 结构化推理链记录。"""

    __tablename__ = "events"

    event_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    event_level: Mapped[str] = mapped_column(String(15), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    producer: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    session: Mapped[CognitiveSession] = relationship(back_populates="events")

    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_events_session_sequence"),
    )


class Checkpoint(Base):
    """检查点表 — 会话状态快照。"""

    __tablename__ = "checkpoints"

    checkpoint_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String(64), server_default="cognitive-rt", nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    state_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    diff: Mapped[dict] = mapped_column(
        JSON, server_default='{"added":[],"removed":[],"modified":[]}', nullable=False
    )
    hot_state: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    full_state_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, server_default="{}", nullable=False)

    session: Mapped[CognitiveSession] = relationship(back_populates="checkpoints")

    __table_args__ = (
        UniqueConstraint("session_id", "version", name="uq_checkpoint_session_version"),
        CheckConstraint("version >= 1", name="ck_version_positive"),
    )


class EvidenceRecord(Base):
    """证据记录表 — 分析结论的可追溯载体。"""

    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), server_default=EvidenceStatus.DISCOVERED.value, nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, server_default="0.5", nullable=False)
    confidence_level: Mapped[str] = mapped_column(
        String(16), server_default="medium", nullable=False
    )
    confidence_basis: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    source_context_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    source_display_name: Mapped[str] = mapped_column(String(256), server_default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    dimension_refs: Mapped[list] = mapped_column(JSON, server_default="[]", nullable=False)
    step_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_by: Mapped[str] = mapped_column(String(64), server_default="", nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    session: Mapped[CognitiveSession] = relationship(back_populates="evidence_records")

    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_evidence_confidence_score",
        ),
    )


class EvidenceRelation(Base):
    """证据关系表 — 证据间的关系链。"""

    __tablename__ = "evidence_relations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    source_evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="CASCADE"), nullable=False
    )
    target_evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, server_default="1.0", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_evidence_relation_confidence",
        ),
        CheckConstraint("source_evidence_id != target_evidence_id", name="no_self_relation"),
    )


class DimensionResult(Base):
    """七维度评估结果表。"""

    __tablename__ = "dimension_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    dimension_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default=DimensionStatus.PENDING.value, nullable=False
    )
    risk_level: Mapped[str] = mapped_column(String(20), server_default="none", nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    summary: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    session: Mapped[CognitiveSession] = relationship(back_populates="dimension_results")

    __table_args__ = (
        UniqueConstraint("session_id", "dimension_id", name="uq_dimension_session_id"),
    )


class L3Knowledge(Base):
    """L3 知识持久化表 — 持久层知识存储。"""

    __tablename__ = "l3_knowledge"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    freshness: Mapped[str] = mapped_column(
        String(20), server_default=FreshnessStatus.ACTIVE.value, nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, server_default="0.5", nullable=False)
    confidence_data: Mapped[dict] = mapped_column(JSON, server_default="{}", nullable=False)
    source_session_ids: Mapped[list] = mapped_column(JSON, server_default="[]", nullable=False)
    superseded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


# ---------------------------------------------------------------------------
# V2 L0/L1 索引表（Batch 2 — 原始数据与结构化事实）
# ---------------------------------------------------------------------------


class RawContext(Base):
    """L0 原始上下文元数据指针表 — 记录原始文件/仓库的元信息。"""

    __tablename__ = "raw_context"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    uri: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(20), server_default="upload", nullable=False)
    superseded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("raw_context.id"), nullable=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    metadata_: Mapped[dict] = mapped_column("metadata_", JSON, server_default="{}", nullable=False)

    project: Mapped[Project] = relationship(back_populates="raw_contexts")

    __table_args__ = (
        CheckConstraint(
            "type IN ('document', 'repo_snapshot', 'git_history', 'other')",
            name="ck_raw_context_type",
        ),
        CheckConstraint(
            "source IN ('upload', 'cli', 'mcp')",
            name="ck_raw_context_source",
        ),
    )


class Chunk(Base):
    """L1 文档 Chunk 表 — 文档切分后的结构化文本片段。"""

    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    raw_context_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("raw_context.id", ondelete="SET NULL"), nullable=True
    )
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    text_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    offset_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offset_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_stale: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="chunks")
    raw_context: Mapped[RawContext | None] = relationship(backref="chunks_rel")

    __table_args__ = (
        CheckConstraint(
            "chunk_type IN ('paragraph', 'section', 'heading', 'table', 'list')",
            name="ck_chunks_type",
        ),
    )


class CodeModule(Base):
    """L1 代码模块表 — 模块/类/函数的结构化提取结果。"""

    __tablename__ = "code_modules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    module_type: Mapped[str] = mapped_column(String(20), nullable=False)
    qualified_name: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_stale: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="code_modules_list")

    __table_args__ = (
        CheckConstraint(
            "module_type IN ('module', 'class', 'function', 'method')",
            name="ck_code_modules_type",
        ),
    )


class CodeDependency(Base):
    """L1 代码依赖关系表 — 模块间依赖关系。"""

    __tablename__ = "code_dependencies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_module_id: Mapped[UUID] = mapped_column(
        ForeignKey("code_modules.id", ondelete="CASCADE"), nullable=False
    )
    target_module_id: Mapped[UUID] = mapped_column(
        ForeignKey("code_modules.id", ondelete="CASCADE"), nullable=False
    )
    dep_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_stale: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    project: Mapped[Project] = relationship()

    __table_args__ = (
        CheckConstraint(
            "dep_type IN ('import', 'call', 'inherit', 'compose')",
            name="ck_code_deps_type",
        ),
        CheckConstraint(
            "source_module_id != target_module_id",
            name="ck_code_deps_no_self",
        ),
    )


class GitCommit(Base):
    """L1 Git 提交事实表 — 仓库提交历史的结构化记录。"""

    __tablename__ = "git_commits"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    commit_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    author_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    changed_files: Mapped[list] = mapped_column(JSON, server_default="[]", nullable=False)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_stale: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="git_commits")


class RequirementCodeLink(Base):
    """L1 需求-代码关联表 — 需求文档与代码模块之间的关联证据。"""

    __tablename__ = "requirement_code_links"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), nullable=True
    )
    code_module_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("code_modules.id", ondelete="CASCADE"), nullable=True
    )
    link_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, server_default="0.5", nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_stale: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    project: Mapped[Project] = relationship()

    __table_args__ = (
        CheckConstraint(
            "link_type IN ('filename_match', 'annotation', 'llm_inferred', 'rule_match')",
            name="ck_req_code_links_type",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_req_code_links_confidence",
        ),
    )


class OutputTask(Base):
    """输出任务表 — 报告生成任务持久化。"""

    __tablename__ = "output_tasks"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), server_default="pending", nullable=False)
    output_format: Mapped[str] = mapped_column(String(20), server_default="markdown", nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    output_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    error: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
