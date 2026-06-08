"""V2 P1: Create L0/L1 index tables.

创建 Batch 2 的 6 张 L0/L1 索引表：
  raw_context, chunks, code_modules, code_dependencies,
  git_commits, requirement_code_links

依赖：V2_P1_create_base_tables（users, projects 基础表必须已存在）

Revision ID: a3f7c2e1b9d4
Revises: V2_P1_create_base_tables
Create Date: 2026-06-04
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "a3f7c2e1b9d4"
down_revision: Union[str, None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 2.1 raw_context — L0 原始上下文元数据指针
    # UUID 主键使用 sa.Uuid()，Python 侧 default=uuid4 生成 ID（兼容 SQLite）
    op.create_table(
        "raw_context",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("uri", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="upload"),
        sa.Column(
            "superseded_by",
            sa.Uuid(),
            sa.ForeignKey("raw_context.id"),
            nullable=True,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("metadata_", sa.JSON(), nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "type IN ('document', 'repo_snapshot', 'git_history', 'other')",
            name="ck_raw_context_type",
        ),
        sa.CheckConstraint(
            "source IN ('upload', 'cli', 'mcp')",
            name="ck_raw_context_source",
        ),
    )
    op.create_index("idx_raw_context_project", "raw_context", ["project_id", "type"])
    op.create_index("idx_raw_context_hash", "raw_context", ["content_hash"])
    op.create_index("idx_raw_context_superseded", "raw_context", ["superseded_by"])

    # 2.2 chunks — L1 文档 Chunk
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "raw_context_id",
            sa.Uuid(),
            sa.ForeignKey("raw_context.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("chunk_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("text_uri", sa.String(500), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("offset_start", sa.Integer(), nullable=True),
        sa.Column("offset_end", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_path", sa.String(500), nullable=True),
        sa.Column("embedding_id", sa.String(100), nullable=True),
        sa.Column(
            "is_stale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
            "chunk_type IN ('paragraph', 'section', 'heading', 'table', 'list')",
            name="ck_chunks_type",
        ),
    )
    op.create_index("idx_chunks_project", "chunks", ["project_id", "chunk_type"])
    op.create_index("idx_chunks_raw_context", "chunks", ["raw_context_id"])
    op.create_index("idx_chunks_embedding", "chunks", ["embedding_id"])
    op.create_index("idx_chunks_stale", "chunks", ["project_id", "is_stale"])

    # 2.3 code_modules — L1 代码模块/类/函数
    op.create_table(
        "code_modules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module_type", sa.String(20), nullable=False),
        sa.Column("qualified_name", sa.String(500), nullable=False),
        sa.Column("short_name", sa.String(100), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("embedding_id", sa.String(100), nullable=True),
        sa.Column(
            "is_stale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
            "module_type IN ('module', 'class', 'function', 'method')",
            name="ck_code_modules_type",
        ),
    )
    op.create_index(
        "idx_code_modules_project",
        "code_modules",
        ["project_id", "module_type"],
    )
    op.create_index(
        "idx_code_modules_qualified",
        "code_modules",
        ["project_id", "qualified_name"],
    )
    op.create_index("idx_code_modules_file", "code_modules", ["project_id", "file_path"])
    op.create_index("idx_code_modules_embedding", "code_modules", ["embedding_id"])
    op.create_index("idx_code_modules_stale", "code_modules", ["project_id", "is_stale"])

    # 2.4 code_dependencies — L1 代码依赖关系
    op.create_table(
        "code_dependencies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_module_id",
            sa.Uuid(),
            sa.ForeignKey("code_modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_module_id",
            sa.Uuid(),
            sa.ForeignKey("code_modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dep_type", sa.String(20), nullable=False),
        sa.Column(
            "is_stale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "dep_type IN ('import', 'call', 'inherit', 'compose')",
            name="ck_code_deps_type",
        ),
        sa.CheckConstraint(
            "source_module_id != target_module_id",
            name="ck_code_deps_no_self",
        ),
    )
    op.create_index("idx_code_deps_source", "code_dependencies", ["source_module_id"])
    op.create_index("idx_code_deps_target", "code_dependencies", ["target_module_id"])
    op.create_index(
        "idx_code_deps_project",
        "code_dependencies",
        ["project_id", "dep_type"],
    )

    # 2.5 git_commits — L1 Git 提交事实
    op.create_table(
        "git_commits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_hash", sa.String(40), nullable=False),
        sa.Column("author", sa.String(200), nullable=False),
        sa.Column("author_email", sa.String(200), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("changed_files", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("diff_summary", sa.Text(), nullable=True),
        sa.Column(
            "is_stale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_git_commits_project",
        "git_commits",
        ["project_id", "committed_at"],
    )
    op.create_index(
        "idx_git_commits_hash",
        "git_commits",
        ["project_id", "commit_hash"],
        unique=True,
    )
    op.create_index("idx_git_commits_author", "git_commits", ["project_id", "author"])

    # 2.6 requirement_code_links — L1 需求-代码关联
    op.create_table(
        "requirement_code_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.Uuid(),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "code_module_id",
            sa.Uuid(),
            sa.ForeignKey("code_modules.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("link_type", sa.String(20), nullable=False),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="0.5",
        ),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column(
            "is_stale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "link_type IN ('filename_match', 'annotation', 'llm_inferred', 'rule_match')",
            name="ck_req_code_links_type",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_req_code_links_confidence",
        ),
    )
    op.create_index(
        "idx_req_code_links_project",
        "requirement_code_links",
        ["project_id", "link_type"],
    )
    op.create_index("idx_req_code_links_chunk", "requirement_code_links", ["chunk_id"])
    op.create_index(
        "idx_req_code_links_module",
        "requirement_code_links",
        ["code_module_id"],
    )


def downgrade() -> None:
    # 按 FK 依赖逆序删除
    op.drop_table("requirement_code_links")
    op.drop_table("git_commits")
    op.drop_table("code_dependencies")
    op.drop_table("code_modules")
    op.drop_table("chunks")
    op.drop_table("raw_context")
