"""price range, estimate method, and Google's per-store price history

The first real google_product capture (2026-10-21) showed two things the
original schema had no place for: a `price_range` band on every product, and
`price_insights`, about a year of dated price changes for each store shown. See
app/models/price_tracking.py (PriceFetch.price_range_*, PriceHistoryPoint) for
what each is and is not trusted for.

Purely additive, like d9e1f3a5b7c2: nothing running reads these yet.

Revision ID: e2a4c6e8f0b1
Revises: d9e1f3a5b7c2
Create Date: 2026-10-21

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "e2a4c6e8f0b1"
down_revision = "d9e1f3a5b7c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_fetches", sa.Column("estimate_method", sa.Text(), nullable=True))
    op.add_column(
        "price_fetches", sa.Column("price_range_low_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "price_fetches", sa.Column("price_range_high_cents", sa.Integer(), nullable=True)
    )

    op.create_table(
        "price_history_points",
        sa.Column(
            "binding_id",
            UUID(as_uuid=True),
            sa.ForeignKey("google_product_bindings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("merchant_name", sa.Text(), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("first_seen_fetch_id", UUID(as_uuid=True), nullable=False),
        sa.Column("last_seen_fetch_id", UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("binding_id", "merchant_name", "price_date"),
    )


def downgrade() -> None:
    op.drop_table("price_history_points")
    op.drop_column("price_fetches", "price_range_high_cents")
    op.drop_column("price_fetches", "price_range_low_cents")
    op.drop_column("price_fetches", "estimate_method")
