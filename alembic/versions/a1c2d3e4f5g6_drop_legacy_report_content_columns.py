"""drop_legacy_report_content_columns

Revision ID: a1c2d3e4f5g6
Revises: 6b1a18e9c17f
Create Date: 2026-05-11 16:19:18.300781

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c2d3e4f5g6"
down_revision: Union[str, Sequence[str], None] = "6b1a18e9c17f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_column("content_markdown")
        batch_op.drop_column("content_html")

    with op.batch_alter_table("report_versions") as batch_op:
        batch_op.drop_column("content_markdown")
        batch_op.drop_column("content_html")


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(
            sa.Column("content_markdown", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("content_html", sa.Text(), nullable=False, server_default=""))

    with op.batch_alter_table("report_versions") as batch_op:
        batch_op.add_column(
            sa.Column("content_markdown", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("content_html", sa.Text(), nullable=False, server_default=""))
