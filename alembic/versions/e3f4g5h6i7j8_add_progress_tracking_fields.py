"""add progress tracking fields to analysis_tasks

Revision ID: e3f4g5h6i7j8
Revises: d4e5f6a7b8c9
Create Date: 2026-05-22 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e3f4g5h6i7j8'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('analysis_tasks', sa.Column('current_step', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('analysis_tasks', sa.Column('progress_snapshot', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('analysis_tasks', 'progress_snapshot')
    op.drop_column('analysis_tasks', 'current_step')
