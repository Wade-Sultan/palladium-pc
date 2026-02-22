import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Listing(Base):
    __tablename__ = "listings"

    __table_args__ = (
        # Same ASIN shouldn't be linked to the same part twice.
        UniqueConstraint("part_id", "asin", name="uq_listings_part_asin"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    part_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Amazon fields
    asin = Column(String(32), nullable=False, index=True)
    url = Column(Text, nullable=True)
    price_cents = Column(
        Integer,
        nullable=True,
        comment="Price in US cents; NULL = not yet fetched / unavailable",
    )
    image_url = Column(Text, nullable=True)

    # Seller info
    seller_name = Column(String(255), nullable=True)
    is_prime = Column(Boolean, nullable=True)

    # Freshness
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    fetched_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When price/availability was last pulled from Amazon",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    part = relationship("PCPart", back_populates="listings")