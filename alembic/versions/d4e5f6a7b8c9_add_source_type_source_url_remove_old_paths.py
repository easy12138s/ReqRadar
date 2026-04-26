"""add source_type/source_url, remove repo_path/docs_path/index_path/config_json

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-04-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('source_type', sa.String(20), nullable=False, server_default='local'))
    op.add_column('projects', sa.Column('source_url', sa.String(1024), nullable=False, server_default=''))
    op.drop_column('projects', 'repo_path')
    op.drop_column('projects', 'docs_path')
    op.drop_column('projects', 'index_path')
    op.drop_column('projects', 'config_json')


def downgrade() -> None:
    op.add_column('projects', sa.Column('repo_path', sa.String(1024), nullable=False, server_default=''))
    op.add_column('projects', sa.Column('docs_path', sa.String(1024), nullable=False, server_default=''))
    op.add_column('projects', sa.Column('index_path', sa.String(1024), nullable=False, server_default=''))
    op.add_column('projects', sa.Column('config_json', sa.Text(), nullable=False, server_default='{}'))
    op.drop_column('projects', 'source_type')
    op.drop_column('projects', 'source_url')
