import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import AUTH_SCHEMA, Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    auth_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{AUTH_SCHEMA}.users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=True,   # nullable during migration; tighten to False later
        index=True,
        comment="FK to Supabase auth.users(id)",
    )

    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)

    hashed_password = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    is_superuser = Column(Boolean, nullable=False, default=False, server_default="false")

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

    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    items = relationship(
        "Item",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str | None:
        return self.username

    @full_name.setter
    def full_name(self, value: str | None) -> None:
        self.username = value
