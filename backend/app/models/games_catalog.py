import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class RequirementTier(str, enum.Enum):
    MINIMUM = "minimum"
    RECOMMENDED = "recommended"
    ULTRA = "ultra"


class Game(Base):
    __tablename__ = "games"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    title = Column(String(255), nullable=False, unique=True)
    slug = Column(String(255), nullable=False, unique=True)  # e.g. "cyberpunk-2077"

    # Community names users actually type: "R6", "Siege" for Rainbow Six Siege;
    # "Val", "Valo" for Valorant. Two jobs, both load-bearing:
    #   1. An exact (normalized) hit here short-circuits the vector search in
    #      services/recommender/catalog_match.py — a known synonym should not be
    #      resolved by approximate nearest neighbour when a string match is
    #      exact and free.
    #   2. They go into the embedded source text, so near-misses ("r6 siege")
    #      still land close in vector space.
    # Curated by hand in the admin panel; nothing infers them.
    aliases = Column(ARRAY(String), nullable=False, server_default="{}")

    genre = Column(
        String(50), nullable=True
    )  # e.g. "aaa_open_world", "competitive_fps"
    store_url = Column(Text, nullable=True)  # Steam, Epic, etc.
    image_url = Column(Text, nullable=True)

    # This is to record features that are absolutely necessary for the title to run at all
    hard_requirements = Column(ARRAY(String), nullable=True)

    min_storage_gb = Column(Integer, nullable=True)

    # Publisher's notes
    requirements_notes = Column(Text, nullable=True)

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

    minimum_parts = relationship(
        "GameMinimumPart",
        back_populates="game",
        cascade="all, delete-orphan",
    )


class GameMinimumPart(Base):
    __tablename__ = "game_minimum_parts"

    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "tier",
            "role",
            "published_name",
            name="uq_game_min_parts_game_tier_role_name",
        ),
        # Postgres treats NULLs as distinct, so the constraint above never
        # fires between two unnamed rows. Restores the old (game, tier, role)
        # guarantee for that case, same pattern as pc_build_parts.
        Index(
            "uq_game_min_parts_game_tier_role_unnamed",
            "game_id",
            "tier",
            "role",
            unique=True,
            postgresql_where=text("published_name IS NULL"),
        ),
        CheckConstraint(
            "gpu_chipset_id IS NULL OR (role = 'gpu' AND part_id IS NULL)",
            name="ck_game_requirement_gpu_target",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    game_id = Column(
        UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Spec level
    tier = Column(String(20), nullable=False)

    # CPU or GPU
    role = Column(String(20), nullable=False)

    part_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_parts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # The marketed name for the part
    published_name = Column(String(255), nullable=True)

    # Published GPU requirements identify silicon, not a board-partner SKU.
    gpu_chipset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("gpu_chipsets.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    min_ram_gb = Column(Integer, nullable=True)

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

    game = relationship("Game", back_populates="minimum_parts")
    part = relationship("PCPart")
    gpu_chipset = relationship("GPUChipset")
