"""add report_versions and report_chats tables

Revision ID: a1b2c3d4e5f6
Revises: 3d6bc67d6a24
Create Date: 2026-04-23 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3d6bc67d6a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('report_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('report_data', sa.Text(), nullable=False),
        sa.Column('context_snapshot', sa.Text(), nullable=False),
        sa.Column('content_markdown', sa.Text(), nullable=False),
        sa.Column('content_html', sa.Text(), nullable=False),
        sa.Column('trigger_type', sa.String(length=50), nullable=False),
        sa.Column('trigger_description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['analysis_tasks.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_versions_task_id'), 'report_versions', ['task_id'], unique=False)
    op.create_table('report_chats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('evidence_refs', sa.Text(), nullable=False),
        sa.Column('intent_type', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['analysis_tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_chats_task_id'), 'report_chats', ['task_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_report_chats_task_id'), table_name='report_chats')
    op.drop_table('report_chats')
    op.drop_index(op.f('ix_report_versions_task_id'), table_name='report_versions')
    op.drop_table('report_versions')
