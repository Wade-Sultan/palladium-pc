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

    category = Column(String(50), nullable=False)

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

class CPU(PCPart):
    pass

class CPUCooler(PCPart):
    pass

class Motherboard(PCPart):
    pass

class RAM(PCPart):
    pass

class Storage(PCPart):
    pass

class GPU(PCPart):
    pass

class Case(PCPart):
    pass

class PSU(PCPart):
    pass

class Fans(PCPart):
    pass