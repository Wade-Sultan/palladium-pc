"""initialize current models

Revision ID: c65f580a6fa6
Revises: 
Create Date: 2026-02-07 10:25:24.747775

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = 'c65f580a6fa6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sa.Enum('draft', 'recommended', 'priced', 'finalized', 'ordered', name='build_status').create(op.get_bind())
    sa.Enum('cpu', 'cpucooler', 'motherboard', 'ram', 'storage', 'gpu', 'psu', 'case', 'fan', name='build_component_role').create(op.get_bind())

    op.create_table('pc_parts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('manufacturer', sa.String(length=255), nullable=True),
    sa.Column('model_number', sa.String(length=255), nullable=True),
    sa.Column('year_released', sa.Integer(), nullable=True),
    sa.Column('part_type', sa.String(length=50), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pc_parts_id'), 'pc_parts', ['id'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('username', sa.String(length=255), nullable=True),
    sa.Column('hashed_password', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('is_superuser', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    op.create_table('conversations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_id'), 'conversations', ['id'], unique=False)
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)

    op.create_table('items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_items_id'), 'items', ['id'], unique=False)

    op.create_table('pc_builds',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('owner_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Enum('draft', 'recommended', 'priced', 'finalized', 'ordered', name='build_status'), nullable=False, server_default='draft'),
    sa.Column('total_price_cents', sa.Integer(), nullable=True),
    sa.Column('use_cases', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('preferences', sa.dialects.postgresql.JSONB(), nullable=True),
    sa.Column('questionnaire_answers', sa.dialects.postgresql.JSONB(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pc_builds_id'), 'pc_builds', ['id'], unique=False)

    op.create_table('pc_build_parts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('build_id', sa.UUID(), nullable=False),
    sa.Column('part_id', sa.UUID(), nullable=True),
    sa.Column('role', sa.Enum('cpu', 'cpucooler', 'motherboard', 'ram', 'storage', 'gpu', 'psu', 'case', 'fan', name='build_component_role'), nullable=False),
    sa.Column('required_component', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('price_at_build_cents', sa.Integer(), nullable=True),
    sa.Column('selection_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['build_id'], ['pc_builds.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['part_id'], ['pc_parts.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('build_id', 'role', name='uq_pc_build_parts_build_role')
    )
    op.create_index(op.f('ix_pc_build_parts_id'), 'pc_build_parts', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_pc_build_parts_id'), table_name='pc_build_parts')
    op.drop_table('pc_build_parts')
    op.drop_index(op.f('ix_pc_builds_id'), table_name='pc_builds')
    op.drop_table('pc_builds')
    op.drop_index(op.f('ix_items_id'), table_name='items')
    op.drop_table('items')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_pc_parts_id'), table_name='pc_parts')
    op.drop_table('pc_parts')
    sa.Enum(name='build_component_role').drop(op.get_bind())
    sa.Enum(name='build_status').drop(op.get_bind())
