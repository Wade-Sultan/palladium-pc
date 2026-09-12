"""Game discovery audit links and GPU requirement alternatives.

Revision ID: a6c8e0f2b4d7
Revises: e5a7c9b1d3f5
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a6c8e0f2b4d7"
down_revision = "e5a7c9b1d3f5"
branch_labels = None
depends_on = None


def upgrade():
    for field in ("matched_game_id", "created_game_id"):
        op.add_column("discovered_items", sa.Column(field, postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f"discovered_items_{field}_fkey", "discovered_items", "games", [field], ["id"], ondelete="SET NULL")
        op.create_index(f"ix_discovered_items_{field}", "discovered_items", [field])
    op.add_column("game_minimum_parts", sa.Column("gpu_chipset_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("game_minimum_parts_gpu_chipset_id_fkey", "game_minimum_parts", "gpu_chipsets", ["gpu_chipset_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_game_minimum_parts_gpu_chipset_id", "game_minimum_parts", ["gpu_chipset_id"])
    op.create_check_constraint("ck_game_requirement_gpu_target", "game_minimum_parts", "gpu_chipset_id IS NULL OR (role = 'gpu' AND part_id IS NULL)")
    op.drop_constraint("uq_game_min_parts_game_tier_role", "game_minimum_parts", type_="unique")
    op.create_unique_constraint("uq_game_min_parts_game_tier_role_name", "game_minimum_parts", ["game_id", "tier", "role", "published_name"])
    # Postgres treats NULLs as distinct, so the constraint above never fires
    # between two unnamed rows. Restores the old (game, tier, role) guarantee
    # for that case.
    op.create_index(
        "uq_game_min_parts_game_tier_role_unnamed",
        "game_minimum_parts",
        ["game_id", "tier", "role"],
        unique=True,
        postgresql_where=sa.text("published_name IS NULL"),
    )


def downgrade():
    # Restoring the old uniqueness rule intentionally fails if alternatives
    # exist. Never silently discard requirement data during a downgrade.
    op.create_unique_constraint("uq_game_min_parts_game_tier_role", "game_minimum_parts", ["game_id", "tier", "role"])
    op.drop_index("uq_game_min_parts_game_tier_role_unnamed", "game_minimum_parts")
    op.drop_constraint("uq_game_min_parts_game_tier_role_name", "game_minimum_parts", type_="unique")
    op.drop_constraint("ck_game_requirement_gpu_target", "game_minimum_parts", type_="check")
    op.drop_column("game_minimum_parts", "gpu_chipset_id")
    for field in ("matched_game_id", "created_game_id"):
        op.drop_column("discovered_items", field)
