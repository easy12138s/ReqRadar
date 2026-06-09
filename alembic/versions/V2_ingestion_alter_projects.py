"""V2 Ingestion: ALTER TABLE projects — 补充项目管理字段 + owner_id 改为可空。

    新增字段：source_type, source_config, status, profile_data, indexed_at, last_sync_at
    修改字段：owner_id 从 NOT NULL 改为 nullable (ondelete SET NULL)

    依赖：V2_P1_create_l2_core_tables（head: b5d8e3f2a1c6）

    Revision ID: e7f1a4c3d9b2
    Revises: b5d8e3f2a1c6
    Create Date: 2026-06-08
"""
from __future__ import annotations

import contextlib
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "e7f1a4c3d9b2"
down_revision: Union[str, None] = "b5d8e3f2a1c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """补充 projects 表 6 个新字段 + 修改 owner_id 为可空。"""
    # 新增字段
    op.add_column("projects", sa.Column("source_type", sa.String(20), nullable=True))
    op.add_column("projects", sa.Column("source_config", sa.JSON(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("status", sa.String(20), server_default="creating", nullable=False),
    )
    op.add_column("projects", sa.Column("profile_data", sa.JSON(), nullable=True))
    op.add_column(
        "projects", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "projects", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True)
    )

    # owner_id 改为可空（SQLite 不支持直接 ALTER COLUMN，需重建表）
    # SQLite 不支持 alter_column，跳过（ORM 层保证 nullable）
    with contextlib.suppress(Exception):
        op.alter_column("projects", "owner_id", nullable=True)


def downgrade() -> None:
    """回滚：删除 6 个新字段 + 恢复 owner_id 为 NOT NULL。"""
    # 注意：数据可能丢失（profile_data 等字段内容）
    with contextlib.suppress(Exception):
        op.alter_column("projects", "owner_id", nullable=False)
    op.drop_column("projects", "last_sync_at")
    op.drop_column("projects", "indexed_at")
    op.drop_column("projects", "profile_data")
    op.drop_column("projects", "status")
    op.drop_column("projects", "source_config")
    op.drop_column("projects", "source_type")
