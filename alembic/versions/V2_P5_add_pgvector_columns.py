"""V2 P5: pgvector 集成 — embedding JSON 列 + vector 列 + HNSW 索引。

    将 chunks、code_modules 的 embedding_id (String) 替换为 embedding (JSON)，
    并在 PostgreSQL 上创建 vector(384) 列和 HNSW 索引。

    注意：
    - embedding JSON 列在 SQLite 和 PG 上同时创建，用于应用层余弦计算
    - embedding_vector vector(384) 列和 HNSW 索引只在 PG 上创建
    - pgvector 扩展只在 PG 上创建（SQLite 跳过）

    依赖：V2_ingestion_alter_projects（head: e7f1a4c3d9b2）

    Revision ID: a9b2c3d4e5f6
    Revises: e7f1a4c3d9b2
    Create Date: 2026-06-12
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "a9b2c3d4e5f6"
down_revision: Union[str, None] = "e7f1a4c3d9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    """检查当前数据库是否为 PostgreSQL。"""
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    """添加/修改嵌入列。"""
    # 1. chunks 表：移除 embedding_id，添加 embedding JSON 列
    with op.batch_alter_table("chunks") as batch_op:
        batch_op.drop_column("embedding_id")
        batch_op.add_column(sa.Column("embedding", sa.JSON(), nullable=True))

    # 2. code_modules 表：移除 embedding_id，添加 embedding JSON 列
    with op.batch_alter_table("code_modules") as batch_op:
        batch_op.drop_column("embedding_id")
        batch_op.add_column(sa.Column("embedding", sa.JSON(), nullable=True))

    # 3. PG 专用：pgvector 扩展 + vector 列 + HNSW 索引
    if _is_postgres():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

        op.add_column("chunks", sa.Column("embedding_vector", sa.Text(), nullable=True))
        op.execute(
            "ALTER TABLE chunks ALTER COLUMN embedding_vector TYPE vector(384) "
            "USING embedding_vector::vector"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_hnsw ON chunks "
            "USING hnsw (embedding_vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )

        op.add_column("code_modules", sa.Column("embedding_vector", sa.Text(), nullable=True))
        op.execute(
            "ALTER TABLE code_modules ALTER COLUMN embedding_vector TYPE vector(384) "
            "USING embedding_vector::vector"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_code_modules_hnsw ON code_modules "
            "USING hnsw (embedding_vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    """回滚。"""
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS idx_chunks_hnsw")
        op.execute("DROP INDEX IF EXISTS idx_code_modules_hnsw")
        op.drop_column("chunks", "embedding_vector")
        op.drop_column("code_modules", "embedding_vector")

    with op.batch_alter_table("chunks") as batch_op:
        batch_op.drop_column("embedding")
        batch_op.add_column(sa.Column("embedding_id", sa.String(100), nullable=True))

    with op.batch_alter_table("code_modules") as batch_op:
        batch_op.drop_column("embedding")
        batch_op.add_column(sa.Column("embedding_id", sa.String(100), nullable=True))
