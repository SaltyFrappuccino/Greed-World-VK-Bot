"""Add Book slot capacity, stable public Card IDs and permanent trophies.

Revision ID: 0012_book_slots_and_trophies
Revises: 0011_character_discussion_sources
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_book_slots_and_trophies"
down_revision: Union[str, None] = "0011_character_discussion_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Two phases avoid collisions with the unique index while shifting the pool.
    op.execute(
        "UPDATE cards SET registry_number = registry_number + 1000000 "
        "WHERE registry_number IS NOT NULL"
    )
    op.execute(
        "UPDATE cards SET registry_number = registry_number - 999900 "
        "WHERE registry_number >= 1000000"
    )

    connection = op.get_bind()
    next_id = int(
        connection.execute(
            sa.text("SELECT COALESCE(MAX(registry_number), 99) + 1 FROM cards")
        ).scalar_one()
    )
    gm_ids = connection.execute(
        sa.text("SELECT id FROM cards WHERE card_type = 'GM' ORDER BY id")
    ).scalars()
    for card_id in gm_ids:
        connection.execute(
            sa.text("UPDATE cards SET registry_number = :number WHERE id = :id"),
            {"number": next_id, "id": card_id},
        )
        next_id += 1

    with op.batch_alter_table("cards") as batch:
        batch.drop_constraint("ck_card_number_pool", type_="check")
        batch.create_check_constraint(
            "ck_card_number_pool",
            "(card_type = 'SPECIAL' AND number IS NOT NULL AND number >= 0 "
            "AND number <= 99 AND registry_number IS NULL) OR "
            "(card_type IN ('SPELL', 'CONTOUR', 'GM') AND number IS NULL "
            "AND registry_number IS NOT NULL AND registry_number >= 100)",
        )

    with op.batch_alter_table("characters") as batch:
        batch.add_column(
            sa.Column("free_slot_limit", sa.Integer(), server_default="10", nullable=False)
        )
        batch.create_check_constraint(
            "ck_character_free_slot_limit", "free_slot_limit >= 10"
        )

    op.create_table(
        "character_trophies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("characters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "rank",
            sa.Enum("BRONZE", "SILVER", "GOLD", name="trophyrank", native_enum=False),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("reward", sa.Text(), server_default="", nullable=False),
        sa.Column("awarded_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_character_trophies_character_id", "character_trophies", ["character_id"])
    op.create_index("ix_character_trophies_name", "character_trophies", ["name"])


def downgrade() -> None:
    op.drop_index("ix_character_trophies_name", table_name="character_trophies")
    op.drop_index("ix_character_trophies_character_id", table_name="character_trophies")
    op.drop_table("character_trophies")

    with op.batch_alter_table("characters") as batch:
        batch.drop_constraint("ck_character_free_slot_limit", type_="check")
        batch.drop_column("free_slot_limit")

    with op.batch_alter_table("cards") as batch:
        batch.drop_constraint("ck_card_number_pool", type_="check")
        batch.create_check_constraint(
            "ck_card_number_pool",
            "(card_type = 'SPECIAL' AND number IS NOT NULL AND number >= 0 "
            "AND number <= 99 AND registry_number IS NULL) OR "
            "(card_type IN ('SPELL', 'CONTOUR') AND number IS NULL "
            "AND registry_number IS NOT NULL AND registry_number >= 0) OR "
            "(card_type = 'GM' AND number IS NULL AND registry_number IS NULL)",
        )

    op.execute("UPDATE cards SET registry_number = NULL WHERE card_type = 'GM'")
    op.execute(
        "UPDATE cards SET registry_number = registry_number + 1000000 "
        "WHERE registry_number IS NOT NULL"
    )
    op.execute(
        "UPDATE cards SET registry_number = registry_number - 1000100 "
        "WHERE registry_number >= 1000000"
    )
