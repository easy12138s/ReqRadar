"""add mcp access keys requirement releases mcp tool calls

Revision ID: 6b95a50161f0
Revises: a1c2d3e4f5g6
Create Date: 2026-05-12 17:35:07.750782

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6b95a50161f0"
down_revision: Union[str, Sequence[str], None] = "a1c2d3e4f5g6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_access_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key_prefix", sa.String(length=12), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_access_keys_key_prefix", "mcp_access_keys", ["key_prefix"])
    op.create_index("ix_mcp_access_keys_user_id", "mcp_access_keys", ["user_id"])

    op.create_table(
        "requirement_releases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("release_code", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["analysis_tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["superseded_by"], ["requirement_releases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_code", "version", name="uq_requirement_release_code_version"),
    )
    op.create_index("ix_requirement_releases_project_id", "requirement_releases", ["project_id"])

    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("access_key_id", sa.Integer(), nullable=True),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["access_key_id"], ["mcp_access_keys.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_tool_calls_access_key_id", "mcp_tool_calls", ["access_key_id"])


def downgrade() -> None:
    op.drop_table("mcp_tool_calls")
    op.drop_table("requirement_releases")
    op.drop_table("mcp_access_keys")
