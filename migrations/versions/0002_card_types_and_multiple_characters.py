"""Add card types and allow several characters per VK account."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_card_types_multi_chars"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

card_type = sa.Enum(
    "SPECIAL",
    "SPELL",
    "ORDINARY",
    "CONTOUR",
    "GM",
    name="cardtype",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column(
        "cards",
        sa.Column(
            "card_type",
            card_type,
            server_default="ORDINARY",
            nullable=False,
        ),
    )
    op.drop_index("ix_characters_vk_id", table_name="characters")
    op.create_index("ix_characters_vk_id", "characters", ["vk_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_characters_vk_id", table_name="characters")
    op.create_index("ix_characters_vk_id", "characters", ["vk_id"], unique=True)
    op.drop_column("cards", "card_type")
