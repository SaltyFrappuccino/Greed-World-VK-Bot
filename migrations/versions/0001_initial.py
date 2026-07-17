"""Initial schema for cards, characters and Shakei transactions."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

rarity = sa.Enum("H", "G", "F", "E", "D", "C", "B", "A", "S", "SS", name="rarity", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("usage", sa.Text(), nullable=False),
        sa.Column("rarity", rarity, nullable=False),
        sa.Column("transform_limit", sa.Integer(), nullable=True),
        sa.Column("copies_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_cards_name", "cards", ["name"], unique=True)

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vk_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("biography", sa.Text(), nullable=False),
        sa.Column("stress_resistance", sa.Integer(), nullable=False),
        sa.Column("speech", sa.Integer(), nullable=False),
        sa.Column("intuition", sa.Integer(), nullable=False),
        sa.Column("spine", sa.Integer(), nullable=False),
        sa.Column("will", sa.Integer(), nullable=False),
        sa.Column("scent", sa.Integer(), nullable=False),
        sa.Column("overall_rating", rarity, nullable=False),
        sa.Column("shakei_balance", sa.Integer(), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_characters_name", "characters", ["name"], unique=False)
    op.create_index("ix_characters_vk_id", "characters", ["vk_id"], unique=True)

    op.create_table(
        "card_ownerships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("obtained_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("card_id", "character_id", name="uq_card_character"),
    )
    op.create_index("ix_card_ownerships_card_id", "card_ownerships", ["card_id"], unique=False)
    op.create_index("ix_card_ownerships_character_id", "card_ownerships", ["character_id"], unique=False)

    op.create_table(
        "shakei_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_character_id", sa.Integer(), nullable=True),
        sa.Column("to_character_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("admin_vk_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["from_character_id"], ["characters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["to_character_id"], ["characters.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shakei_transactions_from_character_id", "shakei_transactions", ["from_character_id"], unique=False)
    op.create_index("ix_shakei_transactions_to_character_id", "shakei_transactions", ["to_character_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shakei_transactions_to_character_id", table_name="shakei_transactions")
    op.drop_index("ix_shakei_transactions_from_character_id", table_name="shakei_transactions")
    op.drop_table("shakei_transactions")
    op.drop_index("ix_card_ownerships_character_id", table_name="card_ownerships")
    op.drop_index("ix_card_ownerships_card_id", table_name="card_ownerships")
    op.drop_table("card_ownerships")
    op.drop_index("ix_characters_vk_id", table_name="characters")
    op.drop_index("ix_characters_name", table_name="characters")
    op.drop_table("characters")
    op.drop_index("ix_cards_name", table_name="cards")
    op.drop_table("cards")
