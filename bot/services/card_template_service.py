from dataclasses import dataclass

from bot.database.models import CardType, Rarity
from bot.services.errors import ValidationError
from bot.utils.templates import parse_labeled_template
from bot.utils.validators import parse_optional_limit, parse_optional_slot_number, parse_rarity


CONTOUR_SUBTYPES: tuple[str, ...] = (
    "Форма — Покров",
    "Форма — Оружие",
    "Форма — Снаряд",
    "Форма — Область",
    "Форма — Ловушка",
    "Форма — Барьер",
    "Эффект — Существо",
    "Эффект — Метка",
    "Эффект — Превращение",
    "Эффект — Связь",
)


@dataclass(frozen=True)
class CardDraft:
    name: str
    card_type: CardType
    kind: str
    rarity: Rarity
    description: str = ""
    usage: str = ""
    transform_limit: int | None = None
    number: int | None = None


_TEMPLATES: dict[CardType, str] = {
    CardType.SPECIAL: """Название:
Номер слота:
Редкость:
Лимит преобразований:
Описание:
Способ использования:""",
    CardType.SPELL: """Название:
Редкость:
Описание эффекта:
Команда активации:
Расходование:""",
    CardType.ORDINARY: """Название:
Вид содержимого:
Редкость:
Описание:
Способ использования:""",
    CardType.CONTOUR: """Название:
Подтип контура:
Редкость:
Описание:
Способ использования:""",
    CardType.GM: """Название:
Редкость:
Описание:
Способ использования:""",
}

_LABELS: dict[CardType, dict[str, str]] = {
    CardType.SPECIAL: {
        "Название": "name",
        "Номер слота": "number",
        "Редкость": "rarity",
        "Лимит преобразований": "transform_limit",
        "Описание": "description",
        "Способ использования": "usage",
    },
    CardType.SPELL: {
        "Название": "name",
        "Редкость": "rarity",
        "Описание эффекта": "description",
        "Команда активации": "activation",
        "Расходование": "consumption",
    },
    CardType.ORDINARY: {
        "Название": "name",
        "Вид содержимого": "kind",
        "Редкость": "rarity",
        "Описание": "description",
        "Способ использования": "usage",
    },
    CardType.CONTOUR: {
        "Название": "name",
        "Подтип контура": "kind",
        "Редкость": "rarity",
        "Описание": "description",
        "Способ использования": "usage",
    },
    CardType.GM: {
        "Название": "name",
        "Редкость": "rarity",
        "Описание": "description",
        "Способ использования": "usage",
    },
}


def template_for(card_type: CardType) -> str:
    return (
        f"Тип карты: {card_type.value}.\n"
        "Скопируйте шаблон, заполните значения после двоеточий и пришлите "
        "одним сообщением. Для пустого необязательного поля поставьте «-».\n\n"
        + _TEMPLATES[card_type]
    )


def parse_card_template(card_type: CardType, text: str) -> CardDraft:
    values = parse_labeled_template(text, _LABELS[card_type])
    for field, title in (("name", "название"), ("rarity", "редкость")):
        if not values.get(field, "").strip():
            raise ValidationError(f"Заполните поле «{title}».")

    kind = card_type.value
    if card_type is CardType.CONTOUR:
        kind = values.get("kind", "").strip()
        if not kind:
            raise ValidationError(
                "Укажите подтип контура, например «Форма — Покров» или «Эффект — Связь»."
            )
    elif card_type is CardType.ORDINARY:
        kind = values.get("kind", "").strip()
        if not kind:
            raise ValidationError("Укажите вид содержимого Обычной карты.")

    description = _optional(values.get("description", ""))
    usage = _optional(values.get("usage", ""))
    number = None
    transform_limit = None

    if card_type is CardType.SPECIAL:
        number_text = values.get("number", "").strip()
        if not number_text or number_text == "-":
            raise ValidationError("У Особой карты обязательно укажите номер слота 0–99.")
        number = parse_optional_slot_number(number_text)
        transform_limit = parse_optional_limit(values.get("transform_limit", "-"))
    elif card_type is CardType.SPELL:
        activation = _optional(values.get("activation", ""))
        consumption = _optional(values.get("consumption", ""))
        usage_parts = []
        if activation:
            usage_parts.append(f"Команда активации: {activation}")
        if consumption:
            usage_parts.append(f"Расходование: {consumption}")
        usage = "\n".join(usage_parts)

    return CardDraft(
        name=values["name"].strip(),
        card_type=card_type,
        kind=kind,
        rarity=parse_rarity(values["rarity"]),
        description=description,
        usage=usage,
        transform_limit=transform_limit,
        number=number,
    )


def parse_card_type(value: str) -> CardType:
    key = value.strip().upper()
    try:
        return CardType[key]
    except KeyError:
        for card_type in CardType:
            if card_type.value.casefold() == value.strip().casefold():
                return card_type
    raise ValidationError("Неизвестный тип карты.")


def _optional(value: str) -> str:
    value = value.strip()
    return "" if value == "-" else value
