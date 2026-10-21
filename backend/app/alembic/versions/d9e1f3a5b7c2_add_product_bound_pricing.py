"""product-bound pricing: bindings, fetches, offers, bins, daily estimates

Prices move from free-text Google Shopping searches to one bound Google product
per SKU, fetched under frozen query conditions, raw responses kept in GCS. See
app/models/price_tracking.py for the shape and why it is separate from
price_checks.

price_merchant_rules is seeded with the US membership warehouses. Seeded here
rather than in code because it is market data an admin edits; ON CONFLICT DO
NOTHING so a re-run never overwrites an edit.

Revision ID: d9e1f3a5b7c2
Revises: c3e5a7b9d1f2
Create Date: 2026-10-20

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "d9e1f3a5b7c2"
down_revision = "c3e5a7b9d1f2"
branch_labels = None
depends_on = None

_KINDS = "'pc_part', 'gpu_chipset', 'psu_group', 'ram_group', 'storage_group'"


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "google_product_bindings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "part_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pc_parts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("google_product_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="candidate"),
        sa.Column("confirmed_by", sa.Text(), nullable=True),
        sa.Column("google_title", sa.Text(), nullable=True),
        sa.Column("match_evidence", JSONB(), nullable=False, server_default="{}"),
        sa.Column("discovery_fetch_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "consecutive_failures", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status_changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.UniqueConstraint(
            "part_id", "google_product_id", name="uq_google_product_bindings_part"
        ),
        sa.CheckConstraint(
            "status IN ('candidate', 'confirmed', 'stale', 'rejected', 'retired')",
            name="ck_google_product_bindings_status",
        ),
        sa.CheckConstraint(
            "confirmed_by IS NULL OR confirmed_by IN ('auto', 'admin')",
            name="ck_google_product_bindings_confirmed_by",
        ),
    )
    op.create_index(
        "ix_google_product_bindings_part_id", "google_product_bindings", ["part_id"]
    )
    op.create_index(
        "uq_google_product_bindings_one_confirmed",
        "google_product_bindings",
        ["part_id"],
        unique=True,
        postgresql_where=sa.text("status = 'confirmed'"),
    )

    op.create_table(
        "price_fetches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pricing_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column(
            "binding_id",
            UUID(as_uuid=True),
            sa.ForeignKey("google_product_bindings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("part_id", UUID(as_uuid=True), nullable=True),
        sa.Column("engine", sa.Text(), nullable=False),
        sa.Column("query_profile_version", sa.Integer(), nullable=False),
        sa.Column("params", JSONB(), nullable=False),
        sa.Column("params_hash", sa.Text(), nullable=False),
        sa.Column("serpapi_search_id", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("raw_uri", sa.Text(), nullable=True),
        sa.Column("raw_sha256", sa.Text(), nullable=True),
        sa.Column("raw_bytes", sa.Integer(), nullable=True),
        sa.Column("estimate_cents", sa.Integer(), nullable=True),
        sa.Column("n_offers_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_offers_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parser_version", sa.Integer(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.CheckConstraint(
            "purpose IN ('offers', 'discovery')", name="ck_price_fetches_purpose"
        ),
    )
    op.create_index("ix_price_fetches_run_id", "price_fetches", ["run_id"])
    op.create_index("ix_price_fetches_binding_id", "price_fetches", ["binding_id"])
    op.create_index("ix_price_fetches_part_id", "price_fetches", ["part_id"])
    op.create_index("ix_price_fetches_fetched_at", "price_fetches", ["fetched_at"])

    op.create_table(
        "price_offers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "fetch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("price_fetches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("merchant_name", sa.Text(), nullable=True),
        sa.Column("merchant_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("original_price_cents", sa.Integer(), nullable=True),
        sa.Column("shipping_cents", sa.Integer(), nullable=True),
        sa.Column("total_cents", sa.Integer(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("flags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("details", JSONB(), nullable=False, server_default="{}"),
        sa.Column("included", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_price_offers_fetch_id", "price_offers", ["fetch_id"])

    op.create_table(
        "price_tracking_state",
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tracked_part_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pc_parts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("bin", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("volatility", sa.Float(), nullable=True),
        sa.Column("n_observations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "volatility_computed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "out_of_top_streak", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "bin_changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("target_kind", "target_id"),
        sa.CheckConstraint(
            f"target_kind IN ({_KINDS})", name="ck_price_tracking_state_kind"
        ),
        sa.CheckConstraint(
            "bin IN ('high', 'medium', 'low')", name="ck_price_tracking_state_bin"
        ),
    )
    op.create_index(
        "ix_price_tracking_state_tracked_part_id",
        "price_tracking_state",
        ["tracked_part_id"],
    )
    op.create_index(
        "ix_price_tracking_state_next_due_at", "price_tracking_state", ["next_due_at"]
    )

    op.create_table(
        "daily_price_estimates",
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("estimate_date", sa.Date(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_fetch_id", UUID(as_uuid=True), nullable=True),
        sa.Column("bin", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.PrimaryKeyConstraint("target_kind", "target_id", "estimate_date"),
        sa.CheckConstraint(
            f"target_kind IN ({_KINDS})", name="ck_daily_price_estimates_kind"
        ),
    )
    op.create_index(
        "ix_daily_price_estimates_estimate_date",
        "daily_price_estimates",
        ["estimate_date"],
    )

    op.create_table(
        "price_merchant_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_pattern", sa.Text(), nullable=False, unique=True),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.CheckConstraint(
            "rule IN ('membership', 'exclude')", name="ck_price_merchant_rules_rule"
        ),
    )
    op.execute(
        """
        INSERT INTO price_merchant_rules (id, merchant_pattern, rule, note)
        VALUES
          (gen_random_uuid(), 'costco', 'membership', 'Warehouse club: member pricing'),
          (gen_random_uuid(), 'sam''s club', 'membership', 'Warehouse club: member pricing'),
          (gen_random_uuid(), 'bj''s', 'membership', 'Warehouse club: member pricing')
        ON CONFLICT (merchant_pattern) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("price_merchant_rules")
    op.drop_index(
        "ix_daily_price_estimates_estimate_date", table_name="daily_price_estimates"
    )
    op.drop_table("daily_price_estimates")
    op.drop_index(
        "ix_price_tracking_state_next_due_at", table_name="price_tracking_state"
    )
    op.drop_index(
        "ix_price_tracking_state_tracked_part_id", table_name="price_tracking_state"
    )
    op.drop_table("price_tracking_state")
    op.drop_index("ix_price_offers_fetch_id", table_name="price_offers")
    op.drop_table("price_offers")
    op.drop_index("ix_price_fetches_fetched_at", table_name="price_fetches")
    op.drop_index("ix_price_fetches_part_id", table_name="price_fetches")
    op.drop_index("ix_price_fetches_binding_id", table_name="price_fetches")
    op.drop_index("ix_price_fetches_run_id", table_name="price_fetches")
    op.drop_table("price_fetches")
    op.drop_index(
        "uq_google_product_bindings_one_confirmed",
        table_name="google_product_bindings",
    )
    op.drop_index(
        "ix_google_product_bindings_part_id", table_name="google_product_bindings"
    )
    op.drop_table("google_product_bindings")
