"""Split card number pools and store ordinary cards directly on ownerships."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_card_pools_ordinary"
down_revision: Union[str, None] = "0004_contour_components_limits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cards") as batch_op:
        batch_op.add_column(sa.Column("registry_number", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint("uq_cards_registry_number", ["registry_number"])

    connection = op.get_bind()
    registry_rows = connection.execute(
        sa.text(
            "SELECT id FROM cards WHERE card_type IN ('SPELL', 'CONTOUR') ORDER BY id"
        )
    ).fetchall()
    for registry_number, row in enumerate(registry_rows):
        connection.execute(
            sa.text("UPDATE cards SET registry_number = :number WHERE id = :card_id"),
            {"number": registry_number, "card_id": row[0]},
        )

    with op.batch_alter_table("card_ownerships") as batch_op:
        batch_op.add_column(sa.Column("ordinary_name", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("ordinary_kind", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("ordinary_description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ordinary_usage", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "ordinary_rarity",
                sa.Enum(
                    "H", "G", "F", "E", "D", "C", "B", "A", "S", "SS",
                    name="rarity",
                    native_enum=False,
                ),
                nullable=True,
            )
        )
        batch_op.alter_column("card_id", existing_type=sa.Integer(), nullable=True)

    connection.execute(
        sa.text(
            """
            UPDATE card_ownerships
            SET ordinary_name = (SELECT name FROM cards WHERE cards.id = card_ownerships.card_id),
                ordinary_kind = (SELECT kind FROM cards WHERE cards.id = card_ownerships.card_id),
                ordinary_description = (SELECT description FROM cards WHERE cards.id = card_ownerships.card_id),
                ordinary_usage = (SELECT usage FROM cards WHERE cards.id = card_ownerships.card_id),
                ordinary_rarity = (SELECT rarity FROM cards WHERE cards.id = card_ownerships.card_id),
                card_id = NULL
            WHERE card_id IN (SELECT id FROM cards WHERE card_type = 'ORDINARY')
            """
        )
    )
    connection.execute(sa.text("DELETE FROM cards WHERE card_type = 'ORDINARY'"))

    with op.batch_alter_table("card_ownerships") as batch_op:
        batch_op.create_check_constraint(
            "ck_ownership_registered_or_ordinary",
            "(card_id IS NOT NULL AND ordinary_name IS NULL) OR "
            "(card_id IS NULL AND ordinary_name IS NOT NULL)",
        )

    with op.batch_alter_table("cards") as batch_op:
        batch_op.create_check_constraint(
            "ck_card_number_pool",
            "(card_type = 'SPECIAL' AND number IS NOT NULL AND number >= 0 AND number <= 99 AND registry_number IS NULL) "
            "OR (card_type IN ('SPELL', 'CONTOUR') AND number IS NULL AND registry_number IS NOT NULL AND registry_number >= 0) "
            "OR (card_type = 'GM' AND number IS NULL AND registry_number IS NULL)",
        )


def downgrade() -> None:
    connection = op.get_bind()
    ordinary_rows = connection.execute(
        sa.text(
            "SELECT DISTINCT ordinary_name, ordinary_kind, ordinary_description, ordinary_usage, ordinary_rarity "
            "FROM card_ownerships WHERE card_id IS NULL"
        )
    ).fetchall()
    for row in ordinary_rows:
        connection.execute(
            sa.text(
                "INSERT INTO cards (name, card_type, kind, description, usage, rarity, copies_count, created_by) "
                "VALUES (:name, 'ORDINARY', :kind, :description, :usage, :rarity, 0, 0)"
            ),
            {
                "name": row[0],
                "kind": row[1] or "Обычная",
                "description": row[2] or "",
                "usage": row[3] or "",
                "rarity": row[4] or "H",
            },
        )
    connection.execute(
        sa.text(
            "UPDATE card_ownerships SET card_id = (SELECT id FROM cards WHERE cards.name = card_ownerships.ordinary_name) "
            "WHERE card_id IS NULL"
        )
    )

    with op.batch_alter_table("cards") as batch_op:
        batch_op.drop_constraint("ck_card_number_pool", type_="check")
    with op.batch_alter_table("card_ownerships") as batch_op:
        batch_op.drop_constraint("ck_ownership_registered_or_ordinary", type_="check")
        batch_op.alter_column("card_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("ordinary_rarity")
        batch_op.drop_column("ordinary_usage")
        batch_op.drop_column("ordinary_description")
        batch_op.drop_column("ordinary_kind")
        batch_op.drop_column("ordinary_name")
    with op.batch_alter_table("cards") as batch_op:
        batch_op.drop_constraint("uq_cards_registry_number", type_="unique")
        batch_op.drop_column("registry_number")
