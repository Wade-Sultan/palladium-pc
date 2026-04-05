"""add_missing_fk_indexes

Revision ID: a8c2e4f61b93
Revises: f55783779a1e
Create Date: 2026-04-04

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a8c2e4f61b93'
down_revision = 'f55783779a1e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_pc_builds_owner_id', 'pc_builds', ['owner_id'])
    op.create_index('ix_pc_build_parts_build_id', 'pc_build_parts', ['build_id'])
    op.create_index('ix_pc_build_parts_part_id', 'pc_build_parts', ['part_id'])
    op.create_index('ix_game_minimum_parts_part_id', 'game_minimum_parts', ['part_id'])
    op.create_index('ix_software_minimum_parts_part_id', 'software_minimum_parts', ['part_id'])


def downgrade() -> None:
    op.drop_index('ix_software_minimum_parts_part_id', table_name='software_minimum_parts')
    op.drop_index('ix_game_minimum_parts_part_id', table_name='game_minimum_parts')
    op.drop_index('ix_pc_build_parts_part_id', table_name='pc_build_parts')
    op.drop_index('ix_pc_build_parts_build_id', table_name='pc_build_parts')
    op.drop_index('ix_pc_builds_owner_id', table_name='pc_builds')
