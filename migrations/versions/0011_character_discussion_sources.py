"""Track the VK discussion comment imported into a character.

Revision ID: 0011_character_discussion_sources
Revises: 0010_approve_admin_characters
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_character_discussion_sources"
down_revision: Union[str, None] = "0010_approve_admin_characters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("characters") as batch:
        batch.add_column(sa.Column("source_group_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("source_topic_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("source_comment_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("source_comment_hash", sa.String(64), nullable=True))
        batch.create_unique_constraint(
            "uq_character_discussion_source",
            ["source_group_id", "source_topic_id", "source_comment_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("characters") as batch:
        batch.drop_constraint("uq_character_discussion_source", type_="unique")
        batch.drop_column("source_comment_hash")
        batch.drop_column("source_comment_id")
        batch.drop_column("source_topic_id")
        batch.drop_column("source_group_id")
