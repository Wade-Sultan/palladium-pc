"""complete systems (DGX Spark, Mac Studio, Strix Halo) as a pc_parts subtype

A system is a machine sold whole. It becomes a `pc_parts` row of part_type
"system" so Amazon listings, the pricing ETL and commerce's by-part listing
lookup all work on it unchanged; see app/models/systems.py for why.

`system_families` is the group table, shaped like gpu_chipsets, and listings
gain a sixth target column for it: an eBay search for "DGX Spark" is right for
every GB10 box, exactly as one "RTX 3090" search is right for every board.
ck_listings_one_target is rebuilt to count the new column.

Revision ID: c3e5a7b9d1f2
Revises: b8d0f2a4c6e9
Create Date: 2026-09-23

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "c3e5a7b9d1f2"
down_revision = "b8d0f2a4c6e9"
branch_labels = None
depends_on = None

_OLD_TARGETS = (
    "part_id",
    "gpu_chipset_id",
    "psu_group_id",
    "ram_group_id",
    "storage_group_id",
)
_NEW_TARGETS = (*_OLD_TARGETS, "system_family_id")


def _one_target(columns: tuple[str, ...]) -> str:
    return " + ".join(f"({c} IS NOT NULL)::int" for c in columns) + " = 1"


def upgrade() -> None:
    op.create_table(
        "system_families",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("gpu_backend", sa.String(20), nullable=False),
        sa.Column("os", sa.String(50), nullable=False),
        sa.Column(
            "suited_for",
            ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strengths", ARRAY(sa.String()), nullable=True),
        sa.Column("limitations", ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_system_families_id", "system_families", ["id"])

    op.create_table(
        "systems",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            sa.ForeignKey("pc_parts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "system_family_id",
            UUID(as_uuid=True),
            sa.ForeignKey("system_families.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("chip", sa.String(100), nullable=False),
        sa.Column("cpu_cores", sa.Integer(), nullable=True),
        sa.Column("gpu_cores", sa.Integer(), nullable=True),
        sa.Column("unified_memory_gb", sa.Integer(), nullable=False),
        sa.Column("gpu_addressable_memory_gb", sa.Integer(), nullable=False),
        sa.Column("memory_bandwidth_gbps", sa.Integer(), nullable=False),
        sa.Column("storage_gb", sa.Integer(), nullable=True),
        sa.Column("tdp_watts", sa.Integer(), nullable=True),
    )
    op.create_index("ix_systems_system_family_id", "systems", ["system_family_id"])

    op.add_column(
        "listings", sa.Column("system_family_id", UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_listings_system_family_id",
        "listings",
        "system_families",
        ["system_family_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_listings_system_family_id", "listings", ["system_family_id"])

    op.drop_constraint("ck_listings_one_target", "listings", type_="check")
    op.create_check_constraint(
        "ck_listings_one_target", "listings", _one_target(_NEW_TARGETS)
    )

    # Commerce resolves a system's family listing through the systems table,
    # the same way e5a7c9b1d3f5 granted it the GPU/PSU/RAM/storage subtypes.
    # Guarded for environments that predate the RLS role split.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'palladium_commerce') THEN
                    GRANT SELECT ON systems, system_families TO palladium_commerce;
                END IF;
            END
            $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'palladium_commerce') THEN
                    REVOKE SELECT ON systems, system_families FROM palladium_commerce;
                END IF;
            END
            $$;
            """
        )
    )

    # Family listings have nothing else to point at once the column goes.
    op.execute(sa.text("DELETE FROM listings WHERE system_family_id IS NOT NULL"))
    op.drop_constraint("ck_listings_one_target", "listings", type_="check")
    op.create_check_constraint(
        "ck_listings_one_target", "listings", _one_target(_OLD_TARGETS)
    )
    op.drop_index("ix_listings_system_family_id", table_name="listings")
    op.drop_constraint("fk_listings_system_family_id", "listings", type_="foreignkey")
    op.drop_column("listings", "system_family_id")

    # pc_parts rows for systems would be orphaned subtype-less rows; drop them.
    op.execute(sa.text("DELETE FROM pc_parts WHERE part_type = 'system'"))
    op.drop_index("ix_systems_system_family_id", table_name="systems")
    op.drop_table("systems")
    op.drop_index("ix_system_families_id", table_name="system_families")
    op.drop_table("system_families")
