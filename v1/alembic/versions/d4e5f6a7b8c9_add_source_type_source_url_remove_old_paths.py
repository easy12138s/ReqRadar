"""add source_type/source_url, remove repo_path/docs_path/index_path/config_json

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-04-26 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column("source_type", sa.String(20), nullable=False, server_default="local")
        )
        batch_op.add_column(
            sa.Column("source_url", sa.String(1024), nullable=False, server_default="")
        )
        batch_op.create_unique_constraint("uq_project_name_owner", ["name", "owner_id"])
        batch_op.drop_column("repo_path")
        batch_op.drop_column("docs_path")
        batch_op.drop_column("index_path")
        batch_op.drop_column("config_json")


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column("repo_path", sa.String(1024), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("docs_path", sa.String(1024), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("index_path", sa.String(1024), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("config_json", sa.Text(), nullable=False, server_default="{}")
        )
        batch_op.drop_constraint("uq_project_name_owner", type_="unique")
        batch_op.drop_column("source_type")
        batch_op.drop_column("source_url")
