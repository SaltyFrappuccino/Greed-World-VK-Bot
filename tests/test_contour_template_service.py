from types import SimpleNamespace

import pytest

from bot.database.crud import characters as characters_crud
from bot.services.contour_template_service import parse_contour_template
from bot.utils import formatters


def test_contour_template_parses_multiline_fields_without_composition():
    fields = parse_contour_template(
        """Название: Гроза
Внешний вид: Искры
Основной эффект:
Покрывает тело молнией.
Не защищает от воды.
Дополнительные возможности:
Условия активации: Назвать имя
Продолжительность: Одна сцена
Проводимость: 1
Влияние на Перегрузку: Один шаг"""
    )

    assert fields["name"] == "Гроза"
    assert fields["primary_effect"] == (
        "Покрывает тело молнией.\nНе защищает от воды."
    )
    assert "composition" not in fields


@pytest.mark.asyncio
async def test_public_character_formatter_never_outputs_private_contours(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    private_contour = SimpleNamespace(name="СЕКРЕТНЫЙ КОНТУР")

    text = formatters.character_profile(character, [], [private_contour])

    assert "СЕКРЕТНЫЙ КОНТУР" not in text
    assert "⌬ Контуры" not in text
