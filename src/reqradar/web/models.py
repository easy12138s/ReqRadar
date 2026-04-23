from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reqradar.web.database import Base


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


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    repo_path: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    docs_path: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    index_path: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    analysis_tasks: Mapped[list["AnalysisTask"]] = relationship(back_populates="project")


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    requirement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    context_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="analysis_tasks")
    user: Mapped["User"] = relationship(back_populates="analysis_tasks")
    report: Mapped["Report | None"] = relationship(back_populates="task", uselist=False)
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(back_populates="task")


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