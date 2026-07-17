from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ShakeiTransaction


async def add_transaction(
    session: AsyncSession,
    *,
    amount: int,
    from_character_id: int | None = None,
    to_character_id: int | None = None,
    reason: str = "",
    admin_vk_id: int | None = None,
) -> ShakeiTransaction:
    transaction = ShakeiTransaction(
        amount=amount,
        from_character_id=from_character_id,
        to_character_id=to_character_id,
        reason=reason,
        admin_vk_id=admin_vk_id,
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def list_history(
    session: AsyncSession, character_id: int, limit: int = 10
) -> list[ShakeiTransaction]:
    stmt = (
        select(ShakeiTransaction)
        .where(
            or_(
                ShakeiTransaction.from_character_id == character_id,
                ShakeiTransaction.to_character_id == character_id,
            )
        )
        .order_by(ShakeiTransaction.created_at.desc(), ShakeiTransaction.id.desc())
        .limit(limit)
    )
    return list(await session.scalars(stmt))


async def sum_incoming(session: AsyncSession, character_id: int) -> int:
    stmt = select(func.coalesce(func.sum(ShakeiTransaction.amount), 0)).where(
        ShakeiTransaction.to_character_id == character_id
    )
    return await session.scalar(stmt) or 0


async def sum_outgoing(session: AsyncSession, character_id: int) -> int:
    stmt = select(func.coalesce(func.sum(ShakeiTransaction.amount), 0)).where(
        ShakeiTransaction.from_character_id == character_id
    )
    return await session.scalar(stmt) or 0
