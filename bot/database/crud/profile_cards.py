from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import CharacterProfileCard


async def get_for_character(
    session: AsyncSession, character_id: int
) -> CharacterProfileCard | None:
    statement = select(CharacterProfileCard).where(
        CharacterProfileCard.character_id == character_id
    )
    return await session.scalar(statement)


async def get_for_character_for_update(
    session: AsyncSession, character_id: int
) -> CharacterProfileCard | None:
    statement = (
        select(CharacterProfileCard)
        .where(CharacterProfileCard.character_id == character_id)
        .with_for_update()
    )
    return await session.scalar(statement)


async def upsert(
    session: AsyncSession,
    *,
    character_id: int,
    input_hash: str,
    storage_key: str,
    file_size: int,
    width: int,
    height: int,
) -> CharacterProfileCard:
    item = await get_for_character_for_update(session, character_id)
    if item is None:
        item = CharacterProfileCard(character_id=character_id)
        session.add(item)
    item.input_hash = input_hash
    item.storage_key = storage_key
    item.file_size = file_size
    item.width = width
    item.height = height
    item.vk_attachment = None
    await session.flush()
    return item
