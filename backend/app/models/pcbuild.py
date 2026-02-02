
import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base  # adjust if needed


class BuildComponentRole(str, enum.Enum):
    CPU = "cpu"
    CPU_COOLER = "cpucooler"
    MOTHERBOARD = "motherboard"
    RAM = "ram"
    STORAGE = "storage"
    GPU = "gpu"
    PSU = "psu"
    CASE = "case"
    FAN = "fan"


class PCBuild(Base):
    __tablename__ = "pc_builds"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

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

    parts = relationship(
        "BuildPart",
        back_populates="build",
        cascade="all, delete-orphan",
    )


class BuildPart(Base):
    """
    Association table between PCBuild and PCPart.

    - role: which "slot" this part fills (cpu, gpu, etc.)
    - required_component: whether this slot must be present for a valid build
      (e.g. CPU=True, GPU=False)
    """

    __tablename__ = "pc_build_parts"

    __table_args__ = (
        UniqueConstraint(
            "build_id",
            "role",
            name="uq_pc_build_parts_build_role",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    build_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_builds.id", ondelete="CASCADE"),
        nullable=False,
    )

    part_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_parts.id", ondelete="SET NULL"),
        nullable=True,
    )

    role = Column(
        Enum(BuildComponentRole, name="build_component_role"),
        nullable=False,
    )

    required_component = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    build = relationship("PCBuild", back_populates="parts")
    part = relationship("PCPart")