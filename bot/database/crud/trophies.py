from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CharacterTrophy, TrophyRank


async def get_by_id(session: AsyncSession, trophy_id: int) -> CharacterTrophy | None:
    return await session.get(CharacterTrophy, trophy_id)


async def get_by_id_for_update(
    session: AsyncSession, trophy_id: int
) -> CharacterTrophy | None:
    return await session.scalar(
        select(CharacterTrophy)
        .where(CharacterTrophy.id == trophy_id)
        .with_for_update()
    )


async def list_for_character(
    session: AsyncSession, character_id: int
) -> list[CharacterTrophy]:
    return list(
        await session.scalars(
            select(CharacterTrophy)
            .where(CharacterTrophy.character_id == character_id)
            .order_by(CharacterTrophy.created_at, CharacterTrophy.id)
        )
    )


async def create(
    session: AsyncSession,
    *,
    character_id: int,
    name: str,
    rank: TrophyRank,
    description: str,
    reward: str,
    awarded_by: int,
) -> CharacterTrophy:
    trophy = CharacterTrophy(
        character_id=character_id,
        name=name,
        rank=rank,
        description=description,
        reward=reward,
        awarded_by=awarded_by,
    )
    session.add(trophy)
    await session.flush()
    return trophy


async def delete(session: AsyncSession, trophy: CharacterTrophy) -> None:
    await session.delete(trophy)
    await session.flush()
