"""Add an audit log for card consumption."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_card_quantities_usage"
down_revision: Union[str, None] = "0006_admin_ai_assistant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("characters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "card_id",
            sa.Integer(),
            sa.ForeignKey("cards.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("character_name", sa.String(128), nullable=False),
        sa.Column("card_name", sa.String(128), nullable=False),
        sa.Column(
            "card_type",
            sa.Enum(
                "SPECIAL", "SPELL", "ORDINARY", "CONTOUR", "GM",
                name="cardtype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("ownership_ids", sa.JSON(), nullable=False),
        sa.Column("used_by_vk_id", sa.BigInteger(), nullable=False),
        sa.Column("target_vk_id", sa.BigInteger(), nullable=True),
        sa.Column("peer_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_message_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_card_usage_quantity_positive"),
    )
    op.create_index("ix_card_usages_character_id", "card_usages", ["character_id"])
    op.create_index("ix_card_usages_card_id", "card_usages", ["card_id"])
    op.create_index("ix_card_usages_used_by_vk_id", "card_usages", ["used_by_vk_id"])
    op.create_index("ix_card_usages_target_vk_id", "card_usages", ["target_vk_id"])
    op.create_index("ix_card_usages_peer_id", "card_usages", ["peer_id"])


def downgrade() -> None:
    op.drop_index("ix_card_usages_peer_id", table_name="card_usages")
    op.drop_index("ix_card_usages_target_vk_id", table_name="card_usages")
    op.drop_index("ix_card_usages_used_by_vk_id", table_name="card_usages")
    op.drop_index("ix_card_usages_card_id", table_name="card_usages")
    op.drop_index("ix_card_usages_character_id", table_name="card_usages")
    op.drop_table("card_usages")
