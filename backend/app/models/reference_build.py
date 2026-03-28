import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ReferenceBuildPart(Base):
    __tablename__ = "reference_build_parts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    build_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reference_builds.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    part_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_parts.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    component  = Column(String(50), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    approx_price = Column(Integer, nullable=False)

    build = relationship("ReferenceBuild", back_populates="parts")
    part  = relationship("PCPart")