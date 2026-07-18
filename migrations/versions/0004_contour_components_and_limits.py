"""Add scalable Contours and bind them to physical card copies."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_contour_components_limits"
down_revision: Union[str, None] = "0003_character_details_contours"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("characters") as batch_op:
        batch_op.add_column(
            sa.Column("contour_limit", sa.Integer(), server_default="2", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_character_contour_limit", "contour_limit >= 2"
        )

    with op.batch_alter_table("contours") as batch_op:
        batch_op.add_column(
            sa.Column("card_capacity", sa.Integer(), server_default="2", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_contour_card_capacity",
            "card_capacity >= 2 AND card_capacity <= 5",
        )

    with op.batch_alter_table("card_ownerships") as batch_op:
        batch_op.drop_constraint("uq_card_character", type_="unique")

    op.create_table(
        "contour_components",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contour_id", sa.Integer(), nullable=False),
        sa.Column("card_ownership_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "position >= 1 AND position <= 5",
            name="ck_contour_component_position",
        ),
        sa.ForeignKeyConstraint(
            ["card_ownership_id"], ["card_ownerships.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["contour_id"], ["contours.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "card_ownership_id", name="uq_contour_component_ownership"
        ),
        sa.UniqueConstraint(
            "contour_id", "position", name="uq_contour_component_position"
        ),
    )
    op.create_index(
        "ix_contour_components_contour_id",
        "contour_components",
        ["contour_id"],
        unique=False,
    )
    op.create_index(
        "ix_contour_components_card_ownership_id",
        "contour_components",
        ["card_ownership_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_contour_components_card_ownership_id", table_name="contour_components"
    )
    op.drop_index(
        "ix_contour_components_contour_id", table_name="contour_components"
    )
    op.drop_table("contour_components")

    with op.batch_alter_table("card_ownerships") as batch_op:
        batch_op.create_unique_constraint(
            "uq_card_character", ["card_id", "character_id"]
        )

    with op.batch_alter_table("contours") as batch_op:
        batch_op.drop_constraint("ck_contour_card_capacity", type_="check")
        batch_op.drop_column("card_capacity")

    with op.batch_alter_table("characters") as batch_op:
        batch_op.drop_constraint("ck_character_contour_limit", type_="check")
        batch_op.drop_column("contour_limit")
