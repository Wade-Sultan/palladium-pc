"""add_missing_fk_indexes

Revision ID: a8c2e4f61b93
Revises: f55783779a1e
Create Date: 2026-04-04

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a8c2e4f61b93'
down_revision = '3a3f1a5b7418'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Missing FK indexes ---
    op.create_index('ix_pc_builds_owner_id', 'pc_builds', ['owner_id'])
    op.create_index('ix_pc_build_parts_build_id', 'pc_build_parts', ['build_id'])
    op.create_index('ix_pc_build_parts_part_id', 'pc_build_parts', ['part_id'])
    op.create_index('ix_game_minimum_parts_part_id', 'game_minimum_parts', ['part_id'])
    op.create_index('ix_software_minimum_parts_part_id', 'software_minimum_parts', ['part_id'])

    # --- SET NULL → RESTRICT on part_id FKs ---
    # Parts are permanent catalog entries; deletion should be blocked if anything references them.
    op.drop_constraint('pc_build_parts_part_id_fkey', 'pc_build_parts', type_='foreignkey')
    op.create_foreign_key(
        'pc_build_parts_part_id_fkey', 'pc_build_parts',
        'pc_parts', ['part_id'], ['id'],
        ondelete='RESTRICT',
    )

    op.drop_constraint('game_minimum_parts_part_id_fkey', 'game_minimum_parts', type_='foreignkey')
    op.create_foreign_key(
        'game_minimum_parts_part_id_fkey', 'game_minimum_parts',
        'pc_parts', ['part_id'], ['id'],
        ondelete='RESTRICT',
    )

    op.drop_constraint('software_minimum_parts_part_id_fkey', 'software_minimum_parts', type_='foreignkey')
    op.create_foreign_key(
        'software_minimum_parts_part_id_fkey', 'software_minimum_parts',
        'pc_parts', ['part_id'], ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    # Revert FK constraints back to SET NULL
    op.drop_constraint('software_minimum_parts_part_id_fkey', 'software_minimum_parts', type_='foreignkey')
    op.create_foreign_key(
        'software_minimum_parts_part_id_fkey', 'software_minimum_parts',
        'pc_parts', ['part_id'], ['id'],
        ondelete='SET NULL',
    )

    op.drop_constraint('game_minimum_parts_part_id_fkey', 'game_minimum_parts', type_='foreignkey')
    op.create_foreign_key(
        'game_minimum_parts_part_id_fkey', 'game_minimum_parts',
        'pc_parts', ['part_id'], ['id'],
        ondelete='SET NULL',
    )

    op.drop_constraint('pc_build_parts_part_id_fkey', 'pc_build_parts', type_='foreignkey')
    op.create_foreign_key(
        'pc_build_parts_part_id_fkey', 'pc_build_parts',
        'pc_parts', ['part_id'], ['id'],
        ondelete='SET NULL',
    )

    # Drop indexes
    op.drop_index('ix_software_minimum_parts_part_id', table_name='software_minimum_parts')
    op.drop_index('ix_game_minimum_parts_part_id', table_name='game_minimum_parts')
    op.drop_index('ix_pc_build_parts_part_id', table_name='pc_build_parts')
    op.drop_index('ix_pc_build_parts_build_id', table_name='pc_build_parts')
    op.drop_index('ix_pc_builds_owner_id', table_name='pc_builds')
