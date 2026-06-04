"""add llm_call_logs table

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-04-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c7d8e9f0a1b2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'llm_call_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('analysis_tasks.id'), nullable=True),
        sa.Column('caller', sa.String(100), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('method', sa.String(50), nullable=False),
        sa.Column('prompt_chars', sa.Integer(), nullable=False),
        sa.Column('completion_chars', sa.Integer(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('tool_calls_count', sa.Integer(), nullable=False),
        sa.Column('tool_names', sa.Text(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_llm_call_logs_task_id', 'llm_call_logs', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_llm_call_logs_task_id')
    op.drop_table('llm_call_logs')
