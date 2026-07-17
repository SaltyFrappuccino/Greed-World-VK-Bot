import pytest

from bot.database.models import CardType, Rarity
from bot.services.card_template_service import parse_card_template
from bot.services.character_template_service import parse_character_template
from bot.services.errors import ValidationError


def test_special_card_template_has_slot_and_limit():
    draft = parse_card_template(
        CardType.SPECIAL,
        """Название: Ясень
Номер слота: 17
Редкость: S
Лимит преобразований: 3
Описание: Ведёт путника.
Способ использования: Сжечь на перекрёстке.""",
    )

    assert draft.number == 17
    assert draft.transform_limit == 3
    assert draft.card_type is CardType.SPECIAL
    assert draft.kind == "Особая"


def test_template_parser_ignores_copied_instruction_before_fields():
    draft = parse_card_template(
        CardType.ORDINARY,
        """Тип карты: Обычная.
Скопируйте шаблон и заполните его:

Название: Верёвка
Редкость: H
Описание: Обычная верёвка
Способ использования: Связать что-нибудь""",
    )

    assert draft.name == "Верёвка"
    assert draft.kind == "Обычная"


def test_spell_template_builds_usage_from_activation_and_consumption():
    draft = parse_card_template(
        CardType.SPELL,
        """Название: Тихий зов
Редкость: A
Описание эффекта: Призывает существо.
Команда активации: Назвать цель
Расходование: Исчезает после применения""",
    )

    assert draft.rarity is Rarity.A
    assert "Команда активации: Назвать цель" in draft.usage
    assert "Расходование: Исчезает после применения" in draft.usage


def test_only_contour_card_asks_for_subtype():
    draft = parse_card_template(
        CardType.CONTOUR,
        """Название: Покров пепла
Подтип контура: Форма — Покров
Редкость: B
Описание: Окутывает владельца.
Способ использования: Вставить в Контур""",
    )

    assert draft.kind == "Форма — Покров"


def test_special_card_requires_slot_number():
    with pytest.raises(ValidationError, match="обязательно укажите номер"):
        parse_card_template(
            CardType.SPECIAL,
            """Название: Без номера
Номер слота: -
Редкость: S
Лимит преобразований: -
Описание: -
Способ использования: -""",
        )


def test_character_template_creates_approved_character_data():
    values = parse_character_template(
        """Имя: Ава
Возраст: 30
Пол: Женский
Внешность: Высокая, книга в серебряном переплёте
Характер: Спокойный
Биография: Первая строка
Вторая строка
Стрессоустойчивость: 5
Речевой аппарат: 4
Чуйка: 3
Хребет: 2
Воля: 5
Нюх: 4
Навыки: ➤ Обучена переговорам
Дополнительно: Боится глубокой воды"""
    )

    assert values["name"] == "Ава"
    assert values["biography"] == "Первая строка\nВторая строка"
    assert values["gender"] == "Женский"
    assert values["skills"] == "➤ Обучена переговорам"
    assert values["is_approved"] is True
    assert values["overall_rating"] is Rarity.H
