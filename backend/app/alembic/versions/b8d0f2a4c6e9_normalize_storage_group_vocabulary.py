"""normalize_storage_group_vocabulary

Storage groups entered by hand through the admin's free-text fields used
`sata` / `sata_ssd` / `2_5_inch` / `3_5_inch`. Code everywhere else uses the
StorageInterface enum and the discovery vocabulary: interface `sata3`,
storage_type `ssd`, form factor `2.5` / `3.5`. The mismatch hid every SATA
drive from the recommender, whose storage query filters on
`interface == 'sata3'` (crud/components.py), and kept its 2.5/3.5-inch bay
count (recommender/validation.py) from ever seeing them. It also meant no
imported SATA drive could ever match one of these groups.

Only the nonstandard spellings are rewritten; any other value is untouched.
Group names are labels, not keys, and are left as they are.

Revision ID: b8d0f2a4c6e9
Revises: d7e9f1a3b5c8
Create Date: 2026-09-22

"""

from alembic import op

revision = "b8d0f2a4c6e9"
down_revision = "d7e9f1a3b5c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE storage_groups SET interface = 'sata3'
        WHERE lower(trim(interface)) = 'sata'
        """
    )
    op.execute(
        """
        UPDATE storage_groups SET storage_type = 'ssd'
        WHERE lower(trim(storage_type)) = 'sata_ssd'
        """
    )
    op.execute(
        """
        UPDATE storage_groups
        SET form_factor = CASE lower(trim(form_factor))
            WHEN '2_5_inch' THEN '2.5' ELSE '3.5' END
        WHERE lower(trim(form_factor)) IN ('2_5_inch', '3_5_inch')
        """
    )


def downgrade() -> None:
    # Not reversible: after upgrade a hand-entered 'sata' row is
    # indistinguishable from one that was always 'sata3', and the old
    # spellings were the bug.
    pass
