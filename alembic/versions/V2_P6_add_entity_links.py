"""add entity_links table

Revision ID: f8e9d0c1b2a3
Revises: a9b2c3d4e5f6
Create Date: 2026-06-29
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "f8e9d0c1b2a3"
down_revision: Union[str, None] = "a9b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entity_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_layer", sa.String(8), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("target_layer", sa.String(8), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("relation_type", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float, server_default="0.5", nullable=False),
        sa.Column("source_session_id", sa.String(36), nullable=True),
        sa.Column("evidence", sa.Text, nullable=True),
        sa.Column("is_stale", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("project_id", "source_type", "source_id", "target_type", "target_id", "relation_type", name="uq_entity_link"),
    )
    op.create_index("ix_entity_links_source", "entity_links", ["project_id", "source_type", "source_id"])
    op.create_index("ix_entity_links_target", "entity_links", ["project_id", "target_type", "target_id"])


def downgrade() -> None:
    op.drop_table("entity_links")
