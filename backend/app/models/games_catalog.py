import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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
    #      services/recommender/catalog_match.py. A known synonym should not be
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
    performance_profiles = relationship(
        "GamePerformanceProfile",
        back_populates="game",
        cascade="all, delete-orphan",
    )
    performance_observations = relationship(
        "GamePerformanceObservation",
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


class GamePerformanceProfile(Base):
    """Versioned performance envelope for one playable game scenario.

    These are deliberately ordinary numeric columns rather than semantic
    embeddings.  A build either clears a measured benchmark/VRAM floor or it
    does not; cosine distance cannot preserve that ordering.  Text embeddings
    continue to resolve a user's free-text title to ``Game`` and this table
    supplies the auditable hardware knowledge after that match.
    """

    __tablename__ = "game_performance_profiles"
    __table_args__ = (
        CheckConstraint("target_fps > 0", name="ck_game_perf_profile_fps_positive"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_game_perf_profile_confidence",
        ),
        CheckConstraint("sample_count >= 0", name="ck_game_perf_profile_sample_count"),
        Index(
            "ix_game_perf_profiles_scenario",
            "game_id",
            "resolution",
            "target_fps",
            "ray_tracing_mode",
            "is_active",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    game_id = Column(
        UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    game_version = Column(String(100), nullable=True)
    resolution = Column(String(20), nullable=False)
    target_fps = Column(Integer, nullable=False)
    quality_preset = Column(String(20), nullable=False, server_default="high")
    ray_tracing_mode = Column(String(30), nullable=False, server_default="off")
    upscaling_mode = Column(String(30), nullable=False, server_default="native")
    frame_generation = Column(Boolean, nullable=False, server_default="false")

    # Floors use the same suite keys carried by CPU/GPU benchmark_scores.
    min_gpu_raster_score = Column(Float, nullable=True)  # Time Spy
    min_gpu_rt_score = Column(Float, nullable=True)  # Port Royal
    min_gpu_modern_score = Column(Float, nullable=True)  # Speed Way
    min_cpu_single_score = Column(Float, nullable=True)
    min_cpu_multi_score = Column(Float, nullable=True)
    min_vram_gb = Column(Integer, nullable=True)
    min_ram_gb = Column(Integer, nullable=True)
    required_features = Column(ARRAY(String), nullable=False, server_default="{}")

    confidence = Column(Float, nullable=False, server_default="0.5")
    sample_count = Column(Integer, nullable=False, server_default="0")
    derivation_method = Column(String(40), nullable=False)
    source_urls = Column(ARRAY(Text), nullable=False, server_default="{}")
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    game = relationship("Game", back_populates="performance_profiles")


class GamePerformanceObservation(Base):
    """One immutable-ish FPS observation used to derive a profile.

    Keeping observations separate means reviewers can disagree without either
    row overwriting the other.  Patch, settings, upscaling and frame generation
    remain attached to the number that was actually measured.
    """

    __tablename__ = "game_performance_observations"
    __table_args__ = (
        CheckConstraint(
            "average_fps > 0", name="ck_game_perf_observation_fps_positive"
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_game_perf_observation_confidence",
        ),
        Index(
            "ix_game_perf_observations_scenario",
            "game_id",
            "resolution",
            "ray_tracing_mode",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    game_id = Column(
        UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gpu_chipset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("gpu_chipsets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cpu_part_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_parts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    game_version = Column(String(100), nullable=True)
    driver_version = Column(String(100), nullable=True)
    resolution = Column(String(20), nullable=False)
    quality_preset = Column(String(20), nullable=False)
    ray_tracing_mode = Column(String(30), nullable=False, server_default="off")
    upscaling_mode = Column(String(30), nullable=False, server_default="native")
    frame_generation = Column(Boolean, nullable=False, server_default="false")
    average_fps = Column(Float, nullable=False)
    p1_fps = Column(Float, nullable=True)
    minimum_fps = Column(Float, nullable=True)

    source_url = Column(Text, nullable=False)
    source_name = Column(String(120), nullable=True)
    source_type = Column(String(40), nullable=False)
    confidence = Column(Float, nullable=False, server_default="0.5")
    metadata_json = Column("metadata", JSONB, nullable=True)
    measured_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    game = relationship("Game", back_populates="performance_observations")
    gpu_chipset = relationship("GPUChipset")
    cpu_part = relationship("PCPart")
