"""Approve existing administrator-created characters.

Revision ID: 0010_approve_admin_characters
Revises: 0009_character_profile_cards
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0010_approve_admin_characters"
down_revision: Union[str, None] = "0009_character_profile_cards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Игроки не создают анкеты: все существующие записи были добавлены админом.
    op.execute("UPDATE characters SET is_approved = 1 WHERE is_approved = 0")


def downgrade() -> None:
    # Исходный статус отдельных записей восстановить достоверно невозможно.
    pass
