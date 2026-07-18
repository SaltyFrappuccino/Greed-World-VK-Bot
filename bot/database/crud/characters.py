from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Character


async def get_by_id(session: AsyncSession, character_id: int) -> Character | None:
    return await session.get(Character, character_id)


async def get_by_id_for_update(session: AsyncSession, character_id: int) -> Character | None:
    stmt = select(Character).where(Character.id == character_id).with_for_update()
    return await session.scalar(stmt)


async def list_by_vk_id(session: AsyncSession, vk_id: int) -> list[Character]:
    stmt = select(Character).where(Character.vk_id == vk_id).order_by(Character.name)
    return list(await session.scalars(stmt))


async def list_characters(
    session: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 10,
    approved_only: bool = True,
) -> list[Character]:
    stmt = select(Character)
    if approved_only:
        stmt = stmt.where(Character.is_approved.is_(True))
    stmt = stmt.order_by(Character.name, Character.id).offset(offset).limit(limit)
    return list(await session.scalars(stmt))


async def count_characters(
    session: AsyncSession, *, approved_only: bool = True
) -> int:
    stmt = select(func.count()).select_from(Character)
    if approved_only:
        stmt = stmt.where(Character.is_approved.is_(True))
    return await session.scalar(stmt) or 0


async def get_owned(
    session: AsyncSession, character_id: int, vk_id: int
) -> Character | None:
    stmt = select(Character).where(Character.id == character_id, Character.vk_id == vk_id)
    return await session.scalar(stmt)


async def get_by_name(session: AsyncSession, name: str) -> Character | None:
    expected = name.strip().casefold()
    characters = await session.scalars(select(Character).order_by(Character.name))
    return next(
        (character for character in characters if character.name.casefold() == expected),
        None,
    )


async def search_by_name(session: AsyncSession, query: str, limit: int = 10) -> list[Character]:
    expected = query.strip().casefold()
    characters = await session.scalars(select(Character).order_by(Character.name))
    return [
        character
        for character in characters
        if expected in character.name.casefold()
    ][:limit]


async def list_pending(session: AsyncSession, limit: int = 20) -> list[Character]:
    """Анкеты, ждущие подтверждения админом."""
    stmt = (
        select(Character)
        .where(Character.is_approved.is_(False))
        .order_by(Character.created_at)
        .limit(limit)
    )
    return list(await session.scalars(stmt))


async def create(session: AsyncSession, *, vk_id: int, name: str, **fields: object) -> Character:
    character = Character(vk_id=vk_id, name=name.strip(), **fields)
    session.add(character)
    await session.flush()
    return character


async def update(session: AsyncSession, character: Character, **fields: object) -> Character:
    for key, value in fields.items():
        if not hasattr(character, key):
            raise AttributeError(f"У персонажа нет поля {key!r}")
        setattr(character, key, value)
    await session.flush()
    return character


async def delete(session: AsyncSession, character: Character) -> None:
    await session.delete(character)
    await session.flush()
