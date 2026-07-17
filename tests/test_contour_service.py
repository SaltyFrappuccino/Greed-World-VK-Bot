import pytest

from bot.database.crud import characters as characters_crud
from bot.services import contour_service
from bot.services.errors import ValidationError


@pytest.mark.asyncio
async def test_character_has_two_contour_slots(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    fields = {
        "composition": "Карта Покрова + Пепел",
        "appearance": "Серый плащ",
        "primary_effect": "Защита",
        "additional_capabilities": "Скрывает силуэт",
        "activation_conditions": "Назвать карты",
        "duration": "Одна сцена",
        "conductivity": "Средняя",
        "overload_impact": "Умеренное",
    }

    first = await contour_service.create_contour(
        session, character_id=character.id, name="Первый", admin_vk_id=99, **fields
    )
    second = await contour_service.create_contour(
        session, character_id=character.id, name="Второй", admin_vk_id=99, **fields
    )

    assert (first.slot, second.slot) == (1, 2)
    with pytest.raises(ValidationError, match="заняты оба слота"):
        await contour_service.create_contour(
            session,
            character_id=character.id,
            name="Третий",
            admin_vk_id=99,
            **fields,
        )
