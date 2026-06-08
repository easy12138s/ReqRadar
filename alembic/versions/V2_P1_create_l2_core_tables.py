"""V2 P1: Create L2 core tables.

创建 Batch 3 的 6 张 L2 核心表：
  cognitive_sessions, events, checkpoints,
  evidence_records, evidence_relations, dimension_results

依赖：V2_P1_create_base_tables（users, projects 基础表必须已存在）

Revision ID: b5d8e3f2a1c6
Revises: a3f7c2e1b9d4
Create Date: 2026-06-04
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "b5d8e3f2a1c6"
down_revision: Union[str, None] = "a3f7c2e1b9d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade() -> None:
    if _table_exists("cognitive_sessions"):
        return

    # 3.1 cognitive_sessions — 认知会话表（L2 核心）
    # session_id 使用 sa.Uuid()，Python 侧 default=uuid4 生成 ID（兼容 SQLite）
    op.create_table(
        "cognitive_sessions",
        sa.Column("session_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="CREATED",
        ),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column(
            "last_checkpoint_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_reasoning_steps",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_tool_calls",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("status_history", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_sessions_project_id",
        "cognitive_sessions",
        ["project_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_sessions_user_id",
        "cognitive_sessions",
        ["user_id", sa.text("created_at DESC")],
    )
    # 部分索引：活跃会话（仅 PostgreSQL 生效）
    op.create_index(
        "idx_sessions_status",
        "cognitive_sessions",
        ["status"],
        postgresql_where=sa.text(
            "status IN ('RUNNING','CHECKPOINTING','WAITING_INPUT','CANCELLING')"
        ),
    )
    # 部分索引：可恢复会话（仅 PostgreSQL 生效）
    op.create_index(
        "idx_sessions_recoverable",
        "cognitive_sessions",
        ["status", "last_checkpoint_version"],
        postgresql_where=sa.text("status IN ('FAILED','TIMEOUT') AND last_checkpoint_version > 0"),
    )
    op.create_index("idx_sessions_updated_at", "cognitive_sessions", ["updated_at"])
    # JSONB 表达式索引（仅 PostgreSQL 生效）
    op.create_index(
        "idx_sessions_config_strategy",
        "cognitive_sessions",
        [sa.text("(config->>'context_strategy')")],
    )
    op.create_index(
        "idx_sessions_state_phase",
        "cognitive_sessions",
        [sa.text("(state->>'current_phase')")],
    )

    # 3.2 events — 事件流表（结构化推理链记录）
    op.create_table(
        "events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("event_level", sa.String(15), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("producer", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("session_id", "sequence", name="uq_events_session_sequence"),
        sa.CheckConstraint(
            "event_type IN ("
            "'SESSION_CREATED','SESSION_STARTED','SESSION_CHECKPOINTED',"
            "'SESSION_COMPLETED','SESSION_FAILED','SESSION_CANCELLING',"
            "'SESSION_CANCELLED','SESSION_TIMEOUT','SESSION_ABORTED',"
            "'SESSION_WAITING_INPUT','SESSION_RESUMED',"
            "'STEP_STARTED','STEP_COMPLETED',"
            "'TOOL_INVOKED','TOOL_RETURNED','TOOL_RETRY','TOOL_TIMEOUT',"
            "'TOOL_PERMISSION_DENIED','TOOL_CHECKPOINT_FAILED',"
            "'CONTEXT_COLLECTED','CONTEXT_SCORED',"
            "'EVIDENCE_ADDED','DIMENSION_CHANGED'"
            ")",
            name="ck_events_event_type",
        ),
        sa.CheckConstraint(
            "event_level IN ('session','reasoning','cognitive')",
            name="ck_events_event_level",
        ),
    )
    op.create_index("idx_events_session_sequence", "events", ["session_id", "sequence"])
    op.create_index("idx_events_session_type", "events", ["session_id", "event_type"])
    op.create_index("idx_events_session_level", "events", ["session_id", "event_level"])
    op.create_index("idx_events_session_timestamp", "events", ["session_id", "timestamp"])
    # JSONB 表达式索引（仅 PostgreSQL 生效）
    op.create_index(
        "idx_events_payload_step",
        "events",
        [sa.text("(payload->>'step')")],
        postgresql_where=sa.text("payload ? 'step'"),
    )
    op.create_index(
        "idx_events_payload_dimension",
        "events",
        [sa.text("(payload->>'dimension')")],
        postgresql_where=sa.text("payload ? 'dimension'"),
    )

    # 3.3 checkpoints — 检查点表（会话状态快照）
    op.create_table(
        "checkpoints",
        sa.Column("checkpoint_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("previous_version", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_by",
            sa.String(64),
            nullable=False,
            server_default="cognitive-rt",
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("state_summary", sa.JSON(), nullable=False),
        sa.Column(
            "diff",
            sa.JSON(),
            nullable=False,
            server_default='{"added":[],"removed":[],"modified":[]}',
        ),
        sa.Column("hot_state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("full_state_uri", sa.String(512), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("session_id", "version", name="uq_checkpoint_session_version"),
        sa.CheckConstraint(
            "type IN ('STEP_COMPLETE','TOOL_PRE','TOOL_POST','MANUAL','PERIODIC')",
            name="ck_checkpoint_type",
        ),
        sa.CheckConstraint("version >= 1", name="ck_version_positive"),
        # pg_column_size 仅 PostgreSQL 生效，SQLite 跳过
        sa.CheckConstraint(
            "pg_column_size(hot_state) <= 1048576",
            name="ck_hot_state_size",
        ),
        sa.CheckConstraint(
            "previous_version IS NULL OR previous_version < version",
            name="ck_previous_version",
        ),
    )
    op.create_index(
        "idx_checkpoints_session_version",
        "checkpoints",
        ["session_id", sa.text("version DESC")],
    )
    op.create_index("idx_checkpoints_session_type", "checkpoints", ["session_id", "type"])
    op.create_index(
        "idx_checkpoints_session_created",
        "checkpoints",
        ["session_id", sa.text("created_at DESC")],
    )
    # JSONB 表达式索引（仅 PostgreSQL 生效）
    op.create_index(
        "idx_checkpoints_state_phase",
        "checkpoints",
        [sa.text("(state_summary->>'current_phase')")],
    )
    op.create_index(
        "idx_checkpoints_state_step",
        "checkpoints",
        [sa.text("((state_summary->>'current_step')::int)")],
    )
    op.create_index(
        "idx_checkpoints_meta_tool",
        "checkpoints",
        [sa.text("(metadata->>'tool_name')")],
    )
    op.create_index("idx_checkpoints_created_at", "checkpoints", ["created_at"])

    # 3.4 evidence_records — 证据记录表
    # id 使用 String(32)，非 UUID（与 ORM EvidenceRecord.id: str 一致）
    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="discovered",
        ),
        sa.Column(
            "confidence_score",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
        sa.Column(
            "confidence_level",
            sa.String(16),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("confidence_basis", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_context_kind", sa.String(32), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column(
            "source_display_name",
            sa.String(256),
            nullable=False,
            server_default="",
        ),
        sa.Column("content", sa.String(200), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("dimension_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("tool_call_id", sa.String(64), nullable=True),
        sa.Column("verified_by", sa.String(64), nullable=False, server_default=""),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_evidence_confidence_score",
        ),
        sa.CheckConstraint(
            "type IN ("
            "'code_evidence','requirement_ref','architecture_doc',"
            "'git_history','memory_ref','tool_output','inference',"
            "'constraint','risk_indicator','verification_result'"
            ")",
            name="ck_evidence_type",
        ),
        sa.CheckConstraint(
            "status IN ('discovered','verified','challenged','superseded','deprecated')",
            name="ck_evidence_status",
        ),
        sa.CheckConstraint(
            "confidence_level IN ('low','medium','high','very_high')",
            name="ck_evidence_confidence_level",
        ),
        sa.CheckConstraint(
            "source_context_kind IN ("
            "'SOURCE_CODE','REQUIREMENT','ARCH_DOC',"
            "'GIT_HISTORY','MEMORY','INFERRED_KNOWLEDGE'"
            ")",
            name="ck_evidence_context_kind",
        ),
    )
    op.create_index("idx_evidence_session", "evidence_records", ["session_id"])
    op.create_index(
        "idx_evidence_session_type",
        "evidence_records",
        ["session_id", "type"],
    )
    op.create_index(
        "idx_evidence_session_status",
        "evidence_records",
        ["session_id", "status"],
    )
    # GIN 索引（仅 PostgreSQL 生效）
    op.create_index(
        "idx_evidence_dimension",
        "evidence_records",
        ["dimension_refs"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_evidence_confidence",
        "evidence_records",
        ["session_id", "confidence_score"],
    )
    op.create_index("idx_evidence_source_uri", "evidence_records", ["source_uri"])
    op.create_index("idx_evidence_created", "evidence_records", ["created_at"])
    # GIN 索引（仅 PostgreSQL 生效）
    op.create_index(
        "idx_evidence_detail",
        "evidence_records",
        ["detail"],
        postgresql_using="gin",
    )

    # 3.5 evidence_relations — 证据关系表
    # id 使用 String(32)，非 UUID（与 ORM EvidenceRelation.id: str 一致）
    op.create_table(
        "evidence_relations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_evidence_id",
            sa.String(32),
            sa.ForeignKey("evidence_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_evidence_id",
            sa.String(32),
            sa.ForeignKey("evidence_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_evidence_relation_confidence",
        ),
        sa.CheckConstraint(
            "relation_type IN ('DEPENDS_ON','IMPACTS','CONFLICTS_WITH','EVOLVES_FROM','MITIGATES','VIOLATES','DERIVED_FROM','CORROBORATES','SUPERSEDES')",
            name="ck_evidence_relation_type",
        ),
        sa.CheckConstraint(
            "source_evidence_id != target_evidence_id",
            name="no_self_relation",
        ),
    )
    op.create_index(
        "idx_evidence_relation_session",
        "evidence_relations",
        ["session_id"],
    )
    op.create_index(
        "idx_evidence_relation_source",
        "evidence_relations",
        ["source_evidence_id"],
    )
    op.create_index(
        "idx_evidence_relation_target",
        "evidence_relations",
        ["target_evidence_id"],
    )
    op.create_index(
        "idx_evidence_relation_type",
        "evidence_relations",
        ["session_id", "relation_type"],
    )
    op.create_index(
        "idx_evidence_relation_unique",
        "evidence_relations",
        ["source_evidence_id", "target_evidence_id", "relation_type"],
        unique=True,
    )

    # 3.6 dimension_results — 七维度评估结果表
    op.create_table(
        "dimension_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("cognitive_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dimension_id", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="not_started",
        ),
        sa.Column(
            "risk_level",
            sa.String(20),
            nullable=False,
            server_default="none",
        ),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("session_id", "dimension_id", name="uq_dimension_session_id"),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','sufficient','insufficient')",
            name="ck_dimension_status",
        ),
        sa.CheckConstraint(
            "risk_level IN ('none','low','medium','high','critical')",
            name="ck_dimension_risk_level",
        ),
    )
    op.create_index("idx_dimension_session_id", "dimension_results", ["session_id"])
    op.create_index("idx_dimension_status", "dimension_results", ["status"])
    op.create_index("idx_dimension_risk_level", "dimension_results", ["risk_level"])
    op.create_index("idx_dimension_dimension_id", "dimension_results", ["dimension_id"])


def downgrade() -> None:
    # 按 FK 依赖逆序删除
    op.drop_table("dimension_results")
    op.drop_table("evidence_relations")
    op.drop_table("evidence_records")
    op.drop_table("checkpoints")
    op.drop_table("events")
    op.drop_table("cognitive_sessions")
