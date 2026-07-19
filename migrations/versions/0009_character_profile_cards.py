"""Cache generated character profile PNG files."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_character_profile_cards"
down_revision: Union[str, None] = "0008_character_arts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "character_profile_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("characters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), server_default="1200", nullable=False),
        sa.Column("height", sa.Integer(), server_default="1600", nullable=False),
        sa.Column("vk_attachment", sa.String(255), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "character_id", name="uq_character_profile_card_character"
        ),
        sa.UniqueConstraint(
            "storage_key", name="uq_character_profile_card_storage_key"
        ),
        sa.CheckConstraint(
            "file_size > 0", name="ck_character_profile_card_file_size"
        ),
    )
    op.create_index(
        "ix_character_profile_cards_character_id",
        "character_profile_cards",
        ["character_id"],
    )
    op.create_index(
        "ix_character_profile_cards_input_hash",
        "character_profile_cards",
        ["input_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_character_profile_cards_input_hash",
        table_name="character_profile_cards",
    )
    op.drop_index(
        "ix_character_profile_cards_character_id",
        table_name="character_profile_cards",
    )
    op.drop_table("character_profile_cards")
