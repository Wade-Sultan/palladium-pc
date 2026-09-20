"""add game performance profiles and observations

Revision ID: d7e9f1a3b5c8
Revises: a6c8e0f2b4d7
Create Date: 2026-09-19 00:00:00.000000

Game title embeddings answer identity, not performance.  These tables hold the
numeric, versioned evidence needed to compare a requested play scenario with
CPU/GPU benchmark scores while preserving the observations behind each derived
profile.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d7e9f1a3b5c8"
down_revision = "a6c8e0f2b4d7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "game_performance_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_version", sa.String(length=100), nullable=True),
        sa.Column("resolution", sa.String(length=20), nullable=False),
        sa.Column("target_fps", sa.Integer(), nullable=False),
        sa.Column(
            "quality_preset",
            sa.String(length=20),
            server_default="high",
            nullable=False,
        ),
        sa.Column(
            "ray_tracing_mode",
            sa.String(length=30),
            server_default="off",
            nullable=False,
        ),
        sa.Column(
            "upscaling_mode",
            sa.String(length=30),
            server_default="native",
            nullable=False,
        ),
        sa.Column(
            "frame_generation", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("min_gpu_raster_score", sa.Float(), nullable=True),
        sa.Column("min_gpu_rt_score", sa.Float(), nullable=True),
        sa.Column("min_gpu_modern_score", sa.Float(), nullable=True),
        sa.Column("min_cpu_single_score", sa.Float(), nullable=True),
        sa.Column("min_cpu_multi_score", sa.Float(), nullable=True),
        sa.Column("min_vram_gb", sa.Integer(), nullable=True),
        sa.Column("min_ram_gb", sa.Integer(), nullable=True),
        sa.Column(
            "required_features",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("sample_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("derivation_method", sa.String(length=40), nullable=False),
        sa.Column(
            "source_urls",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("target_fps > 0", name="ck_game_perf_profile_fps_positive"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_game_perf_profile_confidence",
        ),
        sa.CheckConstraint(
            "sample_count >= 0", name="ck_game_perf_profile_sample_count"
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_game_performance_profiles_id"), "game_performance_profiles", ["id"]
    )
    op.create_index(
        op.f("ix_game_performance_profiles_game_id"),
        "game_performance_profiles",
        ["game_id"],
    )
    op.create_index(
        "ix_game_perf_profiles_scenario",
        "game_performance_profiles",
        ["game_id", "resolution", "target_fps", "ray_tracing_mode", "is_active"],
    )

    op.create_table(
        "game_performance_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gpu_chipset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cpu_part_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("game_version", sa.String(length=100), nullable=True),
        sa.Column("driver_version", sa.String(length=100), nullable=True),
        sa.Column("resolution", sa.String(length=20), nullable=False),
        sa.Column("quality_preset", sa.String(length=20), nullable=False),
        sa.Column(
            "ray_tracing_mode",
            sa.String(length=30),
            server_default="off",
            nullable=False,
        ),
        sa.Column(
            "upscaling_mode",
            sa.String(length=30),
            server_default="native",
            nullable=False,
        ),
        sa.Column(
            "frame_generation", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("average_fps", sa.Float(), nullable=False),
        sa.Column("p1_fps", sa.Float(), nullable=True),
        sa.Column("minimum_fps", sa.Float(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "average_fps > 0", name="ck_game_perf_observation_fps_positive"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_game_perf_observation_confidence",
        ),
        sa.ForeignKeyConstraint(["cpu_part_id"], ["pc_parts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["gpu_chipset_id"], ["gpu_chipsets.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_game_performance_observations_id"),
        "game_performance_observations",
        ["id"],
    )
    op.create_index(
        op.f("ix_game_performance_observations_game_id"),
        "game_performance_observations",
        ["game_id"],
    )
    op.create_index(
        op.f("ix_game_performance_observations_gpu_chipset_id"),
        "game_performance_observations",
        ["gpu_chipset_id"],
    )
    op.create_index(
        op.f("ix_game_performance_observations_cpu_part_id"),
        "game_performance_observations",
        ["cpu_part_id"],
    )
    op.create_index(
        "ix_game_perf_observations_scenario",
        "game_performance_observations",
        ["game_id", "resolution", "ray_tracing_mode"],
    )


def downgrade():
    op.drop_index(
        "ix_game_perf_observations_scenario", table_name="game_performance_observations"
    )
    op.drop_index(
        op.f("ix_game_performance_observations_cpu_part_id"),
        table_name="game_performance_observations",
    )
    op.drop_index(
        op.f("ix_game_performance_observations_gpu_chipset_id"),
        table_name="game_performance_observations",
    )
    op.drop_index(
        op.f("ix_game_performance_observations_game_id"),
        table_name="game_performance_observations",
    )
    op.drop_index(
        op.f("ix_game_performance_observations_id"),
        table_name="game_performance_observations",
    )
    op.drop_table("game_performance_observations")
    op.drop_index(
        "ix_game_perf_profiles_scenario", table_name="game_performance_profiles"
    )
    op.drop_index(
        op.f("ix_game_performance_profiles_game_id"),
        table_name="game_performance_profiles",
    )
    op.drop_index(
        op.f("ix_game_performance_profiles_id"), table_name="game_performance_profiles"
    )
    op.drop_table("game_performance_profiles")
