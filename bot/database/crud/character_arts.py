from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CharacterArt


async def get_by_id(session: AsyncSession, art_id: int) -> CharacterArt | None:
    return await session.get(CharacterArt, art_id)


async def get_by_id_for_update(
    session: AsyncSession, art_id: int
) -> CharacterArt | None:
    statement = (
        select(CharacterArt)
        .where(CharacterArt.id == art_id)
        .with_for_update()
    )
    return await session.scalar(statement)


async def list_for_character(
    session: AsyncSession, character_id: int
) -> list[CharacterArt]:
    statement = (
        select(CharacterArt)
        .where(CharacterArt.character_id == character_id)
        .order_by(CharacterArt.is_primary.desc(), CharacterArt.created_at, CharacterArt.id)
    )
    return list(await session.scalars(statement))


async def get_primary(
    session: AsyncSession, character_id: int
) -> CharacterArt | None:
    statement = select(CharacterArt).where(
        CharacterArt.character_id == character_id,
        CharacterArt.is_primary.is_(True),
    )
    return await session.scalar(statement)


async def count_for_character(session: AsyncSession, character_id: int) -> int:
    statement = (
        select(func.count())
        .select_from(CharacterArt)
        .where(CharacterArt.character_id == character_id)
    )
    return int(await session.scalar(statement) or 0)


async def get_by_hash(
    session: AsyncSession, character_id: int, sha256: str
) -> CharacterArt | None:
    statement = select(CharacterArt).where(
        CharacterArt.character_id == character_id,
        CharacterArt.sha256 == sha256,
    )
    return await session.scalar(statement)


async def clear_primary(session: AsyncSession, character_id: int) -> None:
    await session.execute(
        update(CharacterArt)
        .where(CharacterArt.character_id == character_id)
        .values(is_primary=False)
    )


async def add(session: AsyncSession, **fields: object) -> CharacterArt:
    art = CharacterArt(**fields)
    session.add(art)
    await session.flush()
    return art


async def delete(session: AsyncSession, art: CharacterArt) -> None:
    await session.delete(art)
    await session.flush()
