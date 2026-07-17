"""Add full character details and Contours."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_character_details_contours"
down_revision: Union[str, None] = "0002_card_types_multi_chars"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("gender", sa.String(length=64), server_default="", nullable=False),
    )
    op.add_column(
        "characters",
        sa.Column("appearance", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "characters",
        sa.Column("skills", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "characters",
        sa.Column("additional", sa.Text(), server_default="", nullable=False),
    )
    op.create_table(
        "contours",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("composition", sa.Text(), nullable=False),
        sa.Column("appearance", sa.Text(), nullable=False),
        sa.Column("primary_effect", sa.Text(), nullable=False),
        sa.Column("additional_capabilities", sa.Text(), nullable=False),
        sa.Column("activation_conditions", sa.Text(), nullable=False),
        sa.Column("duration", sa.Text(), nullable=False),
        sa.Column("conductivity", sa.Text(), nullable=False),
        sa.Column("overload_impact", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "slot", name="uq_character_contour_slot"),
    )
    op.create_index("ix_contours_character_id", "contours", ["character_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_contours_character_id", table_name="contours")
    op.drop_table("contours")
    op.drop_column("characters", "additional")
    op.drop_column("characters", "skills")
    op.drop_column("characters", "appearance")
    op.drop_column("characters", "gender")
