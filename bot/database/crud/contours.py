from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Contour


async def list_for_character(
    session: AsyncSession, character_id: int
) -> list[Contour]:
    stmt = select(Contour).where(Contour.character_id == character_id).order_by(Contour.slot)
    return list(await session.scalars(stmt))


async def create(
    session: AsyncSession,
    *,
    character_id: int,
    slot: int,
    name: str,
    created_by: int,
    **fields: object,
) -> Contour:
    contour = Contour(
        character_id=character_id,
        slot=slot,
        name=name.strip(),
        created_by=created_by,
        **fields,
    )
    session.add(contour)
    await session.flush()
    return contour
