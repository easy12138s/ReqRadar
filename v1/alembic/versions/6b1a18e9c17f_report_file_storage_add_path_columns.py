"""report_file_storage_add_path_columns

Revision ID: 6b1a18e9c17f
Revises: b0c1d2e3f4g5
Create Date: 2026-05-09 12:46:11.582733

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6b1a18e9c17f"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4g5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_revoked_tokens_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("revoked_tokens", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_revoked_tokens_token_hash"), ["token_hash"], unique=True
        )

    op.create_table(
        "requirement_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("consolidated_text", sa.Text(), nullable=False),
        sa.Column("source_files", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_reqdocs_project_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_reqdocs_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("analysis_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("requirement_document_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("focus_areas", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_analysis_tasks_reqdoc_id",
            "requirement_documents",
            ["requirement_document_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_analysis_tasks_template_id", "report_templates", ["template_id"], ["id"]
        )

    with op.batch_alter_table("report_versions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("markdown_path", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("html_path", sa.String(length=512), nullable=True))

    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("markdown_path", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("html_path", sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.drop_column("html_path")
        batch_op.drop_column("markdown_path")

    with op.batch_alter_table("report_versions", schema=None) as batch_op:
        batch_op.drop_column("html_path")
        batch_op.drop_column("markdown_path")

    with op.batch_alter_table("analysis_tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_analysis_tasks_template_id", type_="foreignkey")
        batch_op.drop_constraint("fk_analysis_tasks_reqdoc_id", type_="foreignkey")
        batch_op.drop_column("focus_areas")
        batch_op.drop_column("template_id")
        batch_op.drop_column("requirement_document_id")

    op.drop_table("requirement_documents")

    with op.batch_alter_table("revoked_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_revoked_tokens_token_hash"))

    op.drop_table("revoked_tokens")
