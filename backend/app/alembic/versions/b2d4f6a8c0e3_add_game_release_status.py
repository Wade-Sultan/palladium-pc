"""Add release state to games.

Revision ID: b2d4f6a8c0e3
Revises: f3b5d7e9a1c2

An announced title has no measured performance data, so its profiles are
projections and the recommender treats them differently (see
app/services/recommender/projected_floors.py). Release state is curated data,
not inferred from whether profiles exist. `pc_release_date` is deliberately
PC-specific: a console launch date says nothing about when PC ships.

Existing rows default to `released`: every game in the catalog today was added
from published requirements or measurements of a shipped title.
"""

import sqlalchemy as sa
from alembic import op

revision = "b2d4f6a8c0e3"
down_revision = "f3b5d7e9a1c2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "games",
        sa.Column(
            "release_status",
            sa.String(length=20),
            nullable=False,
            server_default="released",
        ),
    )
    op.add_column("games", sa.Column("pc_release_date", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_games_release_status",
        "games",
        "release_status IN ('announced', 'dated', 'released')",
    )


def downgrade():
    op.drop_constraint("ck_games_release_status", "games", type_="check")
    op.drop_column("games", "pc_release_date")
    op.drop_column("games", "release_status")
