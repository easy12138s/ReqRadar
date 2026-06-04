"""change json columns to json type

Revision ID: b0c1d2e3f4g5
Revises: d4e5f6a7b8c9
Create Date: 2026-04-26 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0c1d2e3f4g5"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("synonym_mappings") as batch_op:
        batch_op.alter_column(
            "code_terms", existing_type=sa.Text(), type_=sa.JSON(), existing_nullable=False
        )
    with op.batch_alter_table("analysis_tasks") as batch_op:
        batch_op.alter_column(
            "context_json", existing_type=sa.Text(), type_=sa.JSON(), existing_nullable=False
        )
    with op.batch_alter_table("report_versions") as batch_op:
        batch_op.alter_column(
            "report_data", existing_type=sa.Text(), type_=sa.JSON(), existing_nullable=False
        )
        batch_op.alter_column(
            "context_snapshot", existing_type=sa.Text(), type_=sa.JSON(), existing_nullable=False
        )
    with op.batch_alter_table("report_chats") as batch_op:
        batch_op.alter_column(
            "evidence_refs", existing_type=sa.Text(), type_=sa.JSON(), existing_nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("report_chats") as batch_op:
        batch_op.alter_column(
            "evidence_refs", existing_type=sa.JSON(), type_=sa.Text(), existing_nullable=False
        )
    with op.batch_alter_table("report_versions") as batch_op:
        batch_op.alter_column(
            "context_snapshot", existing_type=sa.JSON(), type_=sa.Text(), existing_nullable=False
        )
        batch_op.alter_column(
            "report_data", existing_type=sa.JSON(), type_=sa.Text(), existing_nullable=False
        )
    with op.batch_alter_table("analysis_tasks") as batch_op:
        batch_op.alter_column(
            "context_json", existing_type=sa.JSON(), type_=sa.Text(), existing_nullable=False
        )
    with op.batch_alter_table("synonym_mappings") as batch_op:
        batch_op.alter_column(
            "code_terms", existing_type=sa.JSON(), type_=sa.Text(), existing_nullable=False
        )
