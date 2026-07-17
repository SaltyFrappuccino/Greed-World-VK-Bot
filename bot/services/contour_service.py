from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import characters as characters_crud
from bot.database.crud import contours as contours_crud
from bot.database.models import Contour
from bot.services.errors import NotFoundError, ValidationError

MAX_CONTOURS = 2


async def create_contour(
    session: AsyncSession,
    *,
    character_id: int,
    name: str,
    admin_vk_id: int,
    **fields: object,
) -> Contour:
    if not name.strip():
        raise ValidationError("Название Контура не может быть пустым.")
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")

    contours = await contours_crud.list_for_character(session, character_id)
    occupied = {contour.slot for contour in contours}
    slot = next((slot for slot in range(1, MAX_CONTOURS + 1) if slot not in occupied), None)
    if slot is None:
        raise ValidationError(
            f"У персонажа {character.name} уже заняты оба слота Контуров."
        )
    return await contours_crud.create(
        session,
        character_id=character_id,
        slot=slot,
        name=name,
        created_by=admin_vk_id,
        **fields,
    )


async def list_for_character(
    session: AsyncSession, character_id: int
) -> list[Contour]:
    return await contours_crud.list_for_character(session, character_id)
