"""initial migration with config tables

Revision ID: fe250b61cf8f
Revises:
Create Date: 2026-04-23 13:59:43.479956

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fe250b61cf8f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('projects',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('repo_path', sa.String(length=1024), nullable=False),
        sa.Column('docs_path', sa.String(length=1024), nullable=False),
        sa.Column('index_path', sa.String(length=1024), nullable=False),
        sa.Column('config_json', sa.Text(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('analysis_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('requirement_name', sa.String(length=255), nullable=False),
        sa.Column('requirement_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('context_json', sa.Text(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('content_markdown', sa.Text(), nullable=False),
        sa.Column('content_html', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['analysis_tasks.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id')
    )
    op.create_table('uploaded_files',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=1024), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['analysis_tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('system_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('config_key', sa.String(length=255), nullable=False),
        sa.Column('config_value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_configs_config_key'), 'system_configs', ['config_key'], unique=True)
    op.create_table('user_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('config_key', sa.String(length=255), nullable=False),
        sa.Column('config_value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=50), nullable=False),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'config_key', name='uq_user_config_key')
    )
    op.create_index(op.f('ix_user_configs_user_id'), 'user_configs', ['user_id'], unique=False)
    op.create_table('project_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('config_key', sa.String(length=255), nullable=False),
        sa.Column('config_value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=50), nullable=False),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'config_key', name='uq_project_config_key')
    )
    op.create_index(op.f('ix_project_configs_project_id'), 'project_configs', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_project_configs_project_id'), table_name='project_configs')
    op.drop_table('project_configs')
    op.drop_index(op.f('ix_user_configs_user_id'), table_name='user_configs')
    op.drop_table('user_configs')
    op.drop_index(op.f('ix_system_configs_config_key'), table_name='system_configs')
    op.drop_table('system_configs')
    op.drop_table('uploaded_files')
    op.drop_table('reports')
    op.drop_table('analysis_tasks')
    op.drop_table('projects')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
