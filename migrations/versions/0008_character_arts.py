"""Add locally stored character artwork metadata."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_character_arts"
down_revision: Union[str, None] = "0007_card_quantities_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "character_arts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("characters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(500), server_default="", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("vk_attachment", sa.String(255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("character_id", "sha256", name="uq_character_art_hash"),
        sa.UniqueConstraint("storage_key", name="uq_character_art_storage_key"),
        sa.CheckConstraint("file_size > 0", name="ck_character_art_file_size"),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name="ck_character_art_dimensions"
        ),
    )
    op.create_index("ix_character_arts_character_id", "character_arts", ["character_id"])
    op.create_index("ix_character_arts_sha256", "character_arts", ["sha256"])
    op.create_index("ix_character_arts_is_primary", "character_arts", ["is_primary"])


def downgrade() -> None:
    op.drop_index("ix_character_arts_is_primary", table_name="character_arts")
    op.drop_index("ix_character_arts_sha256", table_name="character_arts")
    op.drop_index("ix_character_arts_character_id", table_name="character_arts")
    op.drop_table("character_arts")
