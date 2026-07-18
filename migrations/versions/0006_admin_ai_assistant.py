"""Persist administrator AI assistant sessions, messages and plans."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_admin_ai_assistant"
down_revision: Union[str, None] = "0005_card_pools_ordinary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_ai_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_vk_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_admin_ai_sessions_admin_vk_id", "admin_ai_sessions", ["admin_vk_id"])
    op.create_index("ix_admin_ai_sessions_peer_id", "admin_ai_sessions", ["peer_id"])
    op.create_index("ix_admin_ai_sessions_status", "admin_ai_sessions", ["status"])

    op.create_table(
        "admin_ai_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("admin_ai_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_ai_messages_session_id", "admin_ai_messages", ["session_id"])

    op.create_table(
        "admin_ai_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("admin_ai_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admin_vk_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(48), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("destructive", sa.Boolean(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_admin_ai_plans_session_id", "admin_ai_plans", ["session_id"])
    op.create_index("ix_admin_ai_plans_admin_vk_id", "admin_ai_plans", ["admin_vk_id"])
    op.create_index("ix_admin_ai_plans_status", "admin_ai_plans", ["status"])


def downgrade() -> None:
    op.drop_table("admin_ai_plans")
    op.drop_table("admin_ai_messages")
    op.drop_table("admin_ai_sessions")
