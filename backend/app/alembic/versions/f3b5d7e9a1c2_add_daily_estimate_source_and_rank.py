"""daily estimate provenance and volatility rank

daily_price_estimates.source says where each day's price came from:
  fetch    our own estimate, fetched that day
  history  Google's per-store price history for a day between fetches,
           filled in after the next fetch delivered it
  carried  the last known price carried forward, not yet replaced
  none     nothing known yet
so a consumer can always tell a measured day from an inferred one.

price_tracking_state.volatility_rank is the target's place in the weekly
ranking (1 = most volatile), kept so a bin can be explained after the fact.

Additive, nothing running reads these yet.

Revision ID: f3b5d7e9a1c2
Revises: e2a4c6e8f0b1
Create Date: 2026-10-21

"""

import sqlalchemy as sa
from alembic import op

revision = "f3b5d7e9a1c2"
down_revision = "e2a4c6e8f0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_price_estimates",
        sa.Column("source", sa.Text(), nullable=False, server_default="none"),
    )
    op.create_check_constraint(
        "ck_daily_price_estimates_source",
        "daily_price_estimates",
        "source IN ('fetch', 'history', 'carried', 'none')",
    )
    op.add_column(
        "price_tracking_state", sa.Column("volatility_rank", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("price_tracking_state", "volatility_rank")
    op.drop_constraint(
        "ck_daily_price_estimates_source", "daily_price_estimates", type_="check"
    )
    op.drop_column("daily_price_estimates", "source")
