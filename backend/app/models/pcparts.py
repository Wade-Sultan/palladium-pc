import uuid
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class PCPart(Base):
    __tablename__ = "pc_parts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    name = Column(String(255), nullable=False)
    manufacturer = Column(String(255), nullable=True)
    model_number = Column(String(255), nullable=True)

    part_type = Column(String(50), nullable=False)

    amazon_url = Column(Text, nullable=True)
    amazon_asin = Column(String(32), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

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

    __mapper_args__ = {
        "polymorphic_on": part_type,
        "polymorphic_identity": "part",
    }


class CPU(PCPart):
    __mapper_args__ = {"polymorphic_identity": "cpu"}


class CPUCooler(PCPart):
    __mapper_args__ = {"polymorphic_identity": "cpucooler"}


class Motherboard(PCPart):
    __mapper_args__ = {"polymorphic_identity": "motherboard"}


class RAM(PCPart):
    __mapper_args__ = {"polymorphic_identity": "ram"}


class Storage(PCPart):
    __mapper_args__ = {"polymorphic_identity": "storage"}


class GPU(PCPart):
    __mapper_args__ = {"polymorphic_identity": "gpu"}


class PSU(PCPart):
    __mapper_args__ = {"polymorphic_identity": "psu"}


class Case(PCPart):
    __mapper_args__ = {"polymorphic_identity": "case"}


class Fan(PCPart):
    __mapper_args__ = {"polymorphic_identity": "fan"}
