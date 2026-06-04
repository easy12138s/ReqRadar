"""add memory template synonym tables

Revision ID: 3d6bc67d6a24
Revises: fe250b61cf8f
Create Date: 2026-04-23 18:29:11.064592

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3d6bc67d6a24'
down_revision: Union[str, Sequence[str], None] = 'fe250b61cf8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('report_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('definition', sa.Text(), nullable=False),
        sa.Column('render_template', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pending_changes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('change_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.String(length=200), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=False),
        sa.Column('new_value', sa.Text(), nullable=False),
        sa.Column('diff', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pending_changes_project_id'), 'pending_changes', ['project_id'], unique=False)
    op.create_table('synonym_mappings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('business_term', sa.String(length=200), nullable=False),
        sa.Column('code_terms', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'business_term', name='uq_synonym_project_term')
    )
    op.create_index(op.f('ix_synonym_mappings_project_id'), 'synonym_mappings', ['project_id'], unique=False)
    with op.batch_alter_table('analysis_tasks') as batch_op:
        batch_op.add_column(sa.Column('current_version', sa.Integer(), nullable=False, server_default=sa.text('1')))
        batch_op.add_column(sa.Column('depth', sa.String(length=20), nullable=False, server_default='standard'))
    with op.batch_alter_table('projects') as batch_op:
        batch_op.add_column(sa.Column('default_template_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_projects_default_template_id', 'report_templates', ['default_template_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_constraint('fk_projects_default_template_id', type_='foreignkey')
        batch_op.drop_column('default_template_id')
    with op.batch_alter_table('analysis_tasks') as batch_op:
        batch_op.drop_column('depth')
        batch_op.drop_column('current_version')
    op.drop_index(op.f('ix_synonym_mappings_project_id'), table_name='synonym_mappings')
    op.drop_table('synonym_mappings')
    op.drop_index(op.f('ix_pending_changes_project_id'), table_name='pending_changes')
    op.drop_table('pending_changes')
    op.drop_table('report_templates')
