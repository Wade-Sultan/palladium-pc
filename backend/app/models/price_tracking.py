"""
price_tracking.py
=================
Product-bound pricing: every price comes from one Google Shopping product (a
catalog id SerpApi's `google_product` engine accepts), fetched under one frozen
set of query conditions, with the raw response kept in GCS.

WHY NOT EXTEND price_checks. price_checks records free-text searches: a query
string, whatever titles came back, and a median over the ones that survived
filtering. Two runs of that are not the same measurement, because the result
set moves with Google's ranking. A bound product id is the same measurement
every time, so its history is a price series rather than a series of samples of
different things. Mixing the two in one table would make every volatility
figure computed over it quietly wrong.

THE CHAIN, one row each:
  google_product_bindings   which Google product IS this pc_parts row
  price_fetches             one SerpApi call, its raw object in GCS
  price_offers              one store's offer inside that response
  price_tracking_state      how often a target is fetched (its volatility bin)
  daily_price_estimates     one row per target per day, fetched that day or not

TARGETS. (target_kind, target_id) means what it means everywhere else in the
pricing ETL (crud/pricing_etl.TARGET_MODELS): a pc_parts row, or one of the
four group tables that carry street_price_cents. A group is priced through ONE
bound variant, `price_tracking_state.tracked_part_id`, because every extra
variant is another search against a 1000/month cap.

RAW FIRST. A fetch's response is written to GCS before anything parses it, so a
change to the price rules (what counts as a coupon, which merchants are
membership-only) is a re-parse of history, not a re-purchase of it.
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base

TARGET_KINDS = ("pc_part", "gpu_chipset", "psu_group", "ram_group", "storage_group")

BINDING_STATUSES = ("candidate", "confirmed", "stale", "rejected", "retired")
BINDING_CONFIRMERS = ("auto", "admin")

FETCH_PURPOSES = ("offers", "discovery")

BINS = ("high", "medium", "low")

MERCHANT_RULES = ("membership", "exclude")


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class GoogleProductBinding(Base):
    """A pc_parts row's Google Shopping product id.

    google_product_id is NEVER edited in place. A rebind is a new row and the
    old one moves to `retired`, so every offer ever fetched stays attributable
    to the product it was actually fetched for. Status is the only thing that
    changes on a row.

    Lifecycle: discovery writes `candidate`. A strong identity match is promoted
    to `confirmed` with confirmed_by='auto'; anything weaker waits for an admin.
    Only a `confirmed` binding is ever fetched for offers. Repeated empty
    fetches, or a returned title that fails the identity check (Google merges
    and splits catalog ids), move it to `stale`, which queues rediscovery.
    """

    __tablename__ = "google_product_bindings"
    __table_args__ = (
        UniqueConstraint(
            "part_id", "google_product_id", name="uq_google_product_bindings_part"
        ),
        CheckConstraint(
            _in("status", BINDING_STATUSES), name="ck_google_product_bindings_status"
        ),
        CheckConstraint(
            f"confirmed_by IS NULL OR {_in('confirmed_by', BINDING_CONFIRMERS)}",
            name="ck_google_product_bindings_confirmed_by",
        ),
        # At most one confirmed binding per part: two would mean two price
        # series for one SKU, and the estimate would silently pick one.
        Index(
            "uq_google_product_bindings_one_confirmed",
            "part_id",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    google_product_id = Column(Text, nullable=False)

    status = Column(Text, nullable=False, server_default="candidate")
    confirmed_by = Column(Text, nullable=True)

    # The title Google gave this product when it was discovered, and why the
    # match was trusted (similarity, identity-rule outcome, the query used).
    # An admin reviewing a candidate needs both; so does a later audit of an
    # auto-confirmation.
    google_title = Column(Text, nullable=True)
    match_evidence = Column(JSONB, nullable=False, server_default="{}")
    # Snapshot reference to the discovery fetch, not an FK: price_fetches
    # already points here, and a cycle buys nothing.
    discovery_fetch_id = Column(UUID(as_uuid=True), nullable=True)

    consecutive_failures = Column(Integer, nullable=False, server_default="0")
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)

    status_changed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PriceFetch(Base):
    """One SerpApi call: what was asked, where the raw answer lives, and (once
    parsed) the estimate it produced.

    `params_hash` covers the frozen query conditions only, not the product id
    or query text, so one hash per engine across every run is the proof that
    point-in-time conditions never drifted. See pricing_etl/query_profile.py.
    """

    __tablename__ = "price_fetches"
    __table_args__ = (
        CheckConstraint(
            _in("purpose", FETCH_PURPOSES), name="ck_price_fetches_purpose"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pricing_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    purpose = Column(Text, nullable=False)
    binding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("google_product_bindings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # The SKU this fetch was for, under either purpose. Snapshot reference.
    part_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    engine = Column(Text, nullable=False)
    query_profile_version = Column(Integer, nullable=False)
    # Full request parameters minus the api key.
    params = Column(JSONB, nullable=False)
    params_hash = Column(Text, nullable=False)

    serpapi_search_id = Column(Text, nullable=True)
    http_status = Column(Integer, nullable=True)
    error_detail = Column(Text, nullable=True)

    # gs://<bucket>/<object>. Null only when the search was paid for but the
    # write failed; error_detail then says so, and the response is still parsed
    # from memory rather than thrown away.
    raw_uri = Column(Text, nullable=True)
    raw_sha256 = Column(Text, nullable=True)
    raw_bytes = Column(Integer, nullable=True)

    # Filled by the offer parser. parser_version says which rules produced
    # these figures, so a re-parse can find what it has not yet redone.
    estimate_cents = Column(Integer, nullable=True)
    n_offers_total = Column(Integer, nullable=False, server_default="0")
    n_offers_used = Column(Integer, nullable=False, server_default="0")
    parser_version = Column(Integer, nullable=True)

    fetched_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    offers = relationship(
        "PriceOffer", back_populates="fetch", cascade="all, delete-orphan"
    )


class PriceOffer(Base):
    """One store's offer for a bound product.

    `price_cents` is the item price: pre-tax, excluding shipping, before any
    coupon, rebate or membership price. Shipping and total are stored because
    they are in the response, never because anything averages them. An offer
    that cannot honestly yield that number (used, member-only, coupon-priced)
    is kept with included=false and the reason, the same labelled-negative
    principle as price_checks.raw_results.
    """

    __tablename__ = "price_offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fetch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("price_fetches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    position = Column(Integer, nullable=True)
    merchant_name = Column(Text, nullable=True)
    merchant_id = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    link = Column(Text, nullable=True)

    price_cents = Column(Integer, nullable=True)
    original_price_cents = Column(Integer, nullable=True)
    shipping_cents = Column(Integer, nullable=True)
    total_cents = Column(Integer, nullable=True)

    condition = Column(Text, nullable=False, server_default="unknown")
    flags = Column(ARRAY(Text), nullable=False, server_default="{}")
    # details_and_offers, tag, and any field the parser did not map.
    details = Column(JSONB, nullable=False, server_default="{}")

    included = Column(Boolean, nullable=False, server_default="false")
    exclusion_reason = Column(Text, nullable=True)

    fetch = relationship("PriceFetch", back_populates="offers")


class PriceTrackingState(Base):
    """How often a target is fetched.

    Bins are rank-based over volatility: the 5 most volatile targets are
    `high` (daily), the next 100 `medium` (weekly), everything else `low`
    (biweekly). A target with too little history to rank stays `medium`.
    `out_of_top_streak` is the hysteresis counter that keeps a target from
    flapping out of `high` on one quiet week.
    """

    __tablename__ = "price_tracking_state"
    __table_args__ = (
        PrimaryKeyConstraint("target_kind", "target_id"),
        CheckConstraint(
            _in("target_kind", TARGET_KINDS), name="ck_price_tracking_state_kind"
        ),
        CheckConstraint(_in("bin", BINS), name="ck_price_tracking_state_bin"),
    )

    target_kind = Column(Text, nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False)

    # The SKU whose binding is fetched: the part itself for a pc_part target,
    # one chosen variant for a group. SET NULL, not CASCADE: losing the variant
    # means choosing another, not forgetting the target's history.
    tracked_part_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_parts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    bin = Column(Text, nullable=False, server_default="medium")
    volatility = Column(Float, nullable=True)
    n_observations = Column(Integer, nullable=False, server_default="0")
    volatility_computed_at = Column(DateTime(timezone=True), nullable=True)
    out_of_top_streak = Column(Integer, nullable=False, server_default="0")
    bin_changed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    # Null means due now: a target that has never been fetched sorts first.
    next_due_at = Column(DateTime(timezone=True), nullable=True, index=True)


class DailyPriceEstimate(Base):
    """One row per tracked target per day, whether or not it was fetched.

    A low-bin target is fetched every two weeks but still gets thirteen rows in
    between, each carrying the last observed price forward. `last_observed_at`
    is what keeps that honest: a consumer can always tell a fresh price from a
    carried one.

    Volatility is NOT computed from these rows. Carried-forward days are
    zero-change days by construction, so a series built from them makes a
    rarely fetched target look stable because it is rarely fetched. Volatility
    reads price_fetches (real observations) instead.
    """

    __tablename__ = "daily_price_estimates"
    __table_args__ = (
        PrimaryKeyConstraint("target_kind", "target_id", "estimate_date"),
        CheckConstraint(
            _in("target_kind", TARGET_KINDS), name="ck_daily_price_estimates_kind"
        ),
    )

    target_kind = Column(Text, nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False)
    estimate_date = Column(Date, nullable=False, index=True)

    price_cents = Column(Integer, nullable=True)
    last_observed_at = Column(DateTime(timezone=True), nullable=True)
    source_fetch_id = Column(UUID(as_uuid=True), nullable=True)
    bin = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PriceMerchantRule(Base):
    """Merchants whose listed price is not a public price.

    Data, not code: which retailers price for members only changes with the
    market, so it is a table an admin edits rather than a list in the parser.
    `merchant_pattern` is matched case-insensitively as a substring of the
    store name SerpApi reports.
    """

    __tablename__ = "price_merchant_rules"
    __table_args__ = (
        CheckConstraint(
            _in("rule", MERCHANT_RULES), name="ck_price_merchant_rules_rule"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_pattern = Column(Text, nullable=False, unique=True)
    rule = Column(Text, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
