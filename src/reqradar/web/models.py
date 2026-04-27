from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, Integer, DateTime, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reqradar.web.database import Base
from reqradar.web.enums import TaskStatus, ChangeStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")
    analysis_tasks: Mapped[list["AnalysisTask"]] = relationship(back_populates="user")
    configs: Mapped[list["UserConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserConfig(Base):
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    config_key: Mapped[str] = mapped_column(String(255), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), default="string", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="configs")

    __table_args__ = (UniqueConstraint("user_id", "config_key", name="uq_user_config_key"),)


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), default="string", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    default_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("report_templates.id"), nullable=True
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    analysis_tasks: Mapped[list["AnalysisTask"]] = relationship(back_populates="project")
    configs: Mapped[list["ProjectConfig"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    default_template: Mapped["ReportTemplate | None"] = relationship()

    __table_args__ = (UniqueConstraint("name", "owner_id", name="uq_project_name_owner"),)


class ProjectConfig(Base):
    __tablename__ = "project_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    config_key: Mapped[str] = mapped_column(String(255), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), default="string", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="configs")

    __table_args__ = (UniqueConstraint("project_id", "config_key", name="uq_project_config_key"),)


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    requirement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=TaskStatus.PENDING, nullable=False)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    depth: Mapped[str] = mapped_column(String(20), default="standard", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="analysis_tasks")
    user: Mapped["User"] = relationship(back_populates="analysis_tasks")
    report: Mapped["Report | None"] = relationship(back_populates="task", uselist=False)
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(back_populates="task")
    versions: Mapped[list["ReportVersion"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    chats: Mapped[list["ReportChat"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), unique=True, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    task: Mapped["AnalysisTask"] = relationship(back_populates="report")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    task: Mapped["AnalysisTask"] = relationship(back_populates="uploaded_files")


class PendingChange(Base):
    __tablename__ = "pending_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    new_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    diff: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ChangeStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class SynonymMapping(Base):
    __tablename__ = "synonym_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    business_term: Mapped[str] = mapped_column(String(200), nullable=False)
    code_terms: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "business_term", name="uq_synonym_project_term"),)


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    render_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=True)


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    report_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), default="initial", nullable=False)
    trigger_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    task: Mapped["AnalysisTask"] = relationship(back_populates="versions")
    creator: Mapped["User"] = relationship()


class ReportChat(Base):
    __tablename__ = "report_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    intent_type: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    task: Mapped["AnalysisTask"] = relationship(back_populates="chats")


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), nullable=True, index=True)
    caller: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tool_calls_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_names: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)