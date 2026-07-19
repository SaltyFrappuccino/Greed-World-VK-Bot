from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import Card, CardType, Character, Rarity
from bot.services import character_service, trophy_service
from bot.services.card_template_service import CONTOUR_SUBTYPES
from bot.services.errors import NotFoundError, ValidationError

WRITE_TOOLS = {
    "character_create", "character_import_discussion", "character_link_discussion",
    "character_update", "character_delete", "character_approve",
    "character_set_stat", "character_set_rating", "character_change_owner",
    "card_create", "card_create_and_grant", "card_update", "card_delete",
    "card_grant", "card_revoke", "ordinary_card_grant", "ordinary_card_revoke",
    "contour_create", "contour_update", "contour_disassemble", "contour_limit_set",
    "contour_capacity_set", "contour_card_add", "contour_card_remove",
    "contour_card_replace", "shakei_change",
    "character_art_add", "character_art_set_primary",
    "character_art_update_caption", "character_art_delete",
    "free_slot_limit_set", "trophy_award", "trophy_update", "trophy_delete",
}
ACTION_FIELDS = {
    "character_create": ({"vk_id", "name", "fields", "arts"}, {"vk_id", "name"}),
    "character_import_discussion": (
        {"comment_id", "name", "fields", "owner_vk_id", "include_photos"},
        {"comment_id", "name", "fields"},
    ),
    "character_link_discussion": (
        {"character_id", "comment_id"},
        {"character_id", "comment_id"},
    ),
    "character_update": ({"character_id", "fields"}, {"character_id", "fields"}),
    "character_delete": ({"character_id"}, {"character_id"}),
    "character_approve": ({"character_id"}, {"character_id"}),
    "character_set_stat": ({"character_id", "stat", "value"}, {"character_id", "stat", "value"}),
    "character_set_rating": ({"character_id", "rating"}, {"character_id", "rating"}),
    "character_change_owner": ({"character_id", "vk_id"}, {"character_id", "vk_id"}),
    "card_create": ({"name", "card_type", "kind", "rarity", "number", "description", "usage", "transform_limit"}, {"name", "card_type", "kind", "rarity"}),
    "card_create_and_grant": ({"character_id", "name", "card_type", "kind", "rarity", "number", "description", "usage", "transform_limit", "quantity"}, {"character_id", "name", "card_type", "kind", "rarity"}),
    "card_update": ({"card_id", "fields"}, {"card_id", "fields"}),
    "card_delete": ({"card_id"}, {"card_id"}),
    "card_grant": ({"character_id", "card_id", "quantity"}, {"character_id", "card_id"}),
    "card_revoke": ({"character_id", "card_id", "quantity"}, {"character_id", "card_id"}),
    "ordinary_card_grant": ({"character_id", "name", "kind", "rarity", "description", "usage", "quantity"}, {"character_id", "name", "kind", "rarity"}),
    "ordinary_card_revoke": ({"character_id", "ownership_id", "name", "quantity"}, {"character_id"}),
    "contour_create": ({"character_id", "ownership_ids", "name", "slot", "card_capacity", "fields"}, {"character_id", "ownership_ids", "name"}),
    "contour_update": ({"contour_id", "fields"}, {"contour_id", "fields"}),
    "contour_disassemble": ({"contour_id"}, {"contour_id"}),
    "contour_limit_set": ({"character_id", "value"}, {"character_id", "value"}),
    "contour_capacity_set": ({"contour_id", "value"}, {"contour_id", "value"}),
    "contour_card_add": ({"contour_id", "ownership_id"}, {"contour_id", "ownership_id"}),
    "contour_card_remove": ({"contour_id", "component_id"}, {"contour_id", "component_id"}),
    "contour_card_replace": ({"contour_id", "component_id", "ownership_id"}, {"contour_id", "component_id", "ownership_id"}),
    "shakei_change": ({"character_id", "delta"}, {"character_id", "delta"}),
    "character_art_add": ({"character_id", "source_url", "caption", "make_primary"}, {"character_id", "source_url"}),
    "character_art_set_primary": ({"art_id"}, {"art_id"}),
    "character_art_update_caption": ({"art_id", "caption"}, {"art_id", "caption"}),
    "character_art_delete": ({"art_id"}, {"art_id"}),
    "free_slot_limit_set": ({"character_id", "value"}, {"character_id", "value"}),
    "trophy_award": (
        {"character_id", "name", "rank", "description", "reward"},
        {"character_id", "name", "rank"},
    ),
    "trophy_update": ({"trophy_id", "fields"}, {"trophy_id", "fields"}),
    "trophy_delete": ({"trophy_id"}, {"trophy_id"}),
}
CHARACTER_CREATE_FIELDS = {
    "age", "gender", "appearance", "personality", "biography", "skills", "additional",
    "stress_resistance", "speech", "intuition", "spine", "will", "scent",
    "overall_rating", "is_approved", "contour_limit",
}
CHARACTER_UPDATE_FIELDS = {
    "name", "age", "gender", "appearance", "personality", "biography",
    "skills", "additional",
}
CHARACTER_STAT_FIELDS = {
    "stress_resistance", "speech", "intuition", "spine", "will", "scent",
}
CARD_UPDATE_FIELDS = {
    "name", "kind", "rarity", "number", "description", "usage", "transform_limit",
}

async def _character(session: AsyncSession, character_id: int) -> Character:
    item = await characters_crud.get_by_id(session, character_id)
    if item is None:
        raise NotFoundError(f"Анкета #{character_id} не найдена.")
    return item


async def _card(session: AsyncSession, card_id: int) -> Card:
    item = await cards_crud.get_by_id(session, card_id)
    if item is None:
        raise NotFoundError(f"Карта #{card_id} не найдена.")
    return item


def _character_data(item: Character) -> dict[str, object]:
    return {
        "id": item.id, "vk_id": item.vk_id, "name": item.name, "age": item.age,
        "gender": item.gender, "appearance": item.appearance, "personality": item.personality,
        "biography": item.biography, "skills": item.skills, "additional": item.additional,
        "stress_resistance": item.stress_resistance, "speech": item.speech,
        "intuition": item.intuition, "spine": item.spine, "will": item.will, "scent": item.scent,
        "rating": item.overall_rating.value, "shakei": item.shakei_balance,
        "contour_limit": item.contour_limit, "free_slot_limit": item.free_slot_limit,
        "approved": item.is_approved,
    }


def _card_data(item: Card) -> dict[str, object]:
    return {
        "id": item.id, "number": item.number, "registry_number": item.registry_number,
        "public_id": item.number if item.card_type is CardType.SPECIAL else item.registry_number,
        "name": item.name, "card_type": item.card_type.value, "kind": item.kind,
        "rarity": item.rarity.value, "description": item.description, "usage": item.usage,
        "transform_limit": item.transform_limit, "copies_count": item.copies_count,
    }


def _text(arguments: dict[str, object], key: str) -> str:
    value = str(arguments.get(key, "")).strip()
    if not value:
        raise ValidationError(f"Инструменту не передано поле {key}.")
    return value


def _integer(arguments: dict[str, object], key: str) -> int:
    try:
        value = int(arguments[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError(f"Поле {key} должно быть целым числом.") from error
    if value <= 0:
        raise ValidationError(f"Поле {key} должно быть больше нуля.")
    return value


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValidationError("Ожидалось целое число.") from error


def _dict(arguments: dict[str, object], key: str, *, optional: bool = False) -> dict[str, object]:
    value = arguments.get(key, {} if optional else None)
    if not isinstance(value, dict):
        raise ValidationError(f"Поле {key} должно быть объектом.")
    return dict(value)


def _rarity(value: object) -> Rarity:
    try:
        return Rarity(str(value).upper())
    except ValueError as error:
        raise ValidationError("Неизвестная редкость карты.") from error


def _card_type(value: object) -> CardType:
    text = str(value).strip()
    for item in CardType:
        if text.casefold() in {item.name.casefold(), item.value.casefold()}:
            return item
    raise ValidationError("Неизвестный тип карты.")


def _normalize_card_kind(card_type: CardType, kind: object) -> str:
    raw = str(kind or "").strip()
    if card_type is not CardType.CONTOUR:
        return raw

    normalized = raw.casefold().replace("–", "-").replace("—", "-")
    exact_matches = {
        item.casefold(): item for item in CONTOUR_SUBTYPES
    }
    if normalized in exact_matches:
        return exact_matches[normalized]

    short_matches = {
        item.split("—", 1)[1].strip().casefold(): item
        for item in CONTOUR_SUBTYPES
    }
    short_normalized = normalized
    if short_normalized.startswith("форма") or short_normalized.startswith("эффект"):
        parts = [part.strip() for part in short_normalized.split("-", 1)]
        if len(parts) == 2:
            short_normalized = parts[1]
    if short_normalized in short_matches:
        return short_matches[short_normalized]

    return raw


def _normalize_card_fields(fields: dict[str, object]) -> dict[str, object]:
    if "rarity" in fields:
        fields["rarity"] = _rarity(fields["rarity"])
    if "card_type" in fields:
        raise ValidationError("Тип существующей карты менять нельзя.")
    return fields


def _normalize_character_create_fields(fields: dict[str, object]) -> dict[str, object]:
    _reject_unknown_fields(fields, CHARACTER_CREATE_FIELDS, "новой анкеты")
    if "overall_rating" in fields:
        fields["overall_rating"] = _rarity(fields["overall_rating"])
    return fields


def _reject_unknown_fields(
    fields: dict[str, object], allowed: set[str], target: str
) -> None:
    unknown = set(fields) - allowed
    if unknown:
        raise ValidationError(
            f"AI попытался изменить запрещённые поля {target}: {', '.join(sorted(unknown))}."
        )


def _validate_character_update_fields(
    fields: dict[str, object], character_id: object
) -> None:
    unknown = set(fields) - CHARACTER_UPDATE_FIELDS
    if not unknown:
        return

    corrections: list[str] = []
    stats = sorted(unknown & CHARACTER_STAT_FIELDS)
    if stats:
        actions = "; ".join(
            "character_set_stat "
            f'{{"character_id":{character_id},"stat":"{stat}","value":{fields[stat]}}}'
            for stat in stats
        )
        corrections.append(
            "статы нельзя помещать в character_update.fields; создай отдельное "
            f"действие для каждого стата: {actions}"
        )
    if unknown & {"overall_rating", "rating"}:
        corrections.append(
            "рейтинг меняется через character_set_rating {character_id,rating}"
        )
    if "vk_id" in unknown:
        corrections.append(
            "владелец меняется через character_change_owner {character_id,vk_id}"
        )
    if "contour_limit" in unknown:
        corrections.append(
            "лимит Контуров меняется через contour_limit_set {character_id,value}"
        )
    if unknown & {"shakei", "shakei_balance"}:
        corrections.append(
            "Шакеи меняются через shakei_change {character_id,delta}"
        )

    allowed = ", ".join(sorted(CHARACTER_UPDATE_FIELDS))
    guidance = " ".join(corrections)
    message = (
        "Некорректный character_update: запрещённые поля: "
        f"{', '.join(sorted(unknown))}. Допустимые fields: {allowed}. "
        f"{guidance}"
    )
    raise ValidationError(message.strip())


def _validate_action_arguments(name: str, arguments: dict[str, object]) -> None:
    allowed, required = ACTION_FIELDS[name]
    unknown = set(arguments) - allowed
    missing = required - set(arguments)
    if unknown:
        raise ValidationError(
            f"Инструмент {name} получил запрещённые аргументы: {', '.join(sorted(unknown))}."
        )
    if missing:
        raise ValidationError(
            f"Инструмент {name} не получил обязательные аргументы: {', '.join(sorted(missing))}."
        )
    for key in (
        "vk_id", "character_id", "card_id", "contour_id", "ownership_id",
        "component_id", "art_id", "trophy_id", "comment_id", "owner_vk_id",
    ):
        if key in arguments and arguments[key] not in (None, ""):
            _integer(arguments, key)
    ownership_ids = arguments.get("ownership_ids")
    if ownership_ids is not None:
        if not isinstance(ownership_ids, list):
            raise ValidationError("Поле ownership_ids должно быть списком числовых ID.")
        for value in ownership_ids:
            try:
                if int(value) <= 0:
                    raise ValueError
            except (TypeError, ValueError) as error:
                raise ValidationError(
                    "Каждый элемент ownership_ids должен быть положительным числовым ID."
                ) from error
    if name == "character_create" and "arts" in arguments:
        arts = arguments["arts"]
        if not isinstance(arts, list) or not arts:
            raise ValidationError("Поле arts новой анкеты должно быть непустым списком.")
        for art in arts:
            if not isinstance(art, dict):
                raise ValidationError("Каждый арт новой анкеты должен быть объектом.")
            unknown_art_fields = set(art) - {"source_url", "caption", "make_primary"}
            if unknown_art_fields:
                raise ValidationError("Арт новой анкеты содержит неизвестные поля.")
            _text(art, "source_url")
            if len(str(art.get("caption", ""))) > 500:
                raise ValidationError("Подпись арта не может быть длиннее 500 символов.")
    if name in {"character_create", "character_import_discussion"}:
        _normalize_character_create_fields(
            _dict(arguments, "fields", optional=True)
        )
    if name == "character_update":
        fields = _dict(arguments, "fields")
        _validate_character_update_fields(fields, arguments["character_id"])
    if "quantity" in arguments:
        quantity = _integer(arguments, "quantity")
        if quantity > 999:
            raise ValidationError("Количество карт за одну операцию не может быть больше 999.")
    if "caption" in arguments and len(str(arguments["caption"])) > 500:
        raise ValidationError("Подпись арта не может быть длиннее 500 символов.")
    if name == "ordinary_card_revoke":
        has_ownership = arguments.get("ownership_id") not in (None, "")
        has_name = bool(str(arguments.get("name", "")).strip())
        if has_ownership == has_name:
            raise ValidationError(
                "Для изъятия Обычной карты укажите либо ownership_id одной копии, "
                "либо name и необязательное quantity."
            )
    if name == "free_slot_limit_set" and _integer(arguments, "value") < 10:
        raise ValidationError("Количество Свободных слотов не может быть меньше 10.")
    if name == "trophy_award":
        _text(arguments, "name")
        trophy_service.parse_rank(_text(arguments, "rank"))
    if name == "trophy_update":
        fields = _dict(arguments, "fields")
        unknown = set(fields) - {"name", "rank", "description", "reward"}
        if unknown:
            raise ValidationError(
                "Трофей не имеет полей: " + ", ".join(sorted(unknown)) + "."
            )
        if "rank" in fields:
            trophy_service.parse_rank(str(fields["rank"]))
        if has_ownership and int(arguments.get("quantity", 1)) != 1:
            raise ValidationError(
                "При изъятии по ownership_id количество всегда равно 1; "
                "для нескольких копий используйте name и quantity."
            )
    if name not in {"card_create", "card_create_and_grant"}:
        return

    card_type = _card_type(arguments["card_type"])
    _rarity(arguments["rarity"])
    kind = _normalize_card_kind(card_type, arguments["kind"])
    arguments["kind"] = kind
    if card_type is CardType.ORDINARY:
        raise ValidationError(
            "Обычная карта не создаётся в реестре: используй ordinary_card_grant."
        )
    number = _optional_int(arguments.get("number"))
    transform_limit = _optional_int(arguments.get("transform_limit"))
    if card_type is CardType.SPECIAL:
        if number is None:
            raise ValidationError("Для Особой карты нужен номер слота от 0 до 99.")
        if not 0 <= number <= 99:
            raise ValidationError("Номер Особого слота должен быть от 0 до 99.")
    elif number is not None:
        raise ValidationError("Номер Особого слота допустим только для Особой карты.")
    if card_type is not CardType.SPECIAL and transform_limit is not None:
        raise ValidationError("Лимит преобразований допустим только для Особой карты.")
    if transform_limit is not None and transform_limit < 1:
        raise ValidationError("Лимит преобразований должен быть больше нуля.")
    if card_type is CardType.CONTOUR and kind not in CONTOUR_SUBTYPES:
        raise ValidationError(
            "Контурной карте нужен системный подтип из списка форм или эффектов."
        )
    if card_type is CardType.SPELL and kind.casefold() != CardType.SPELL.value.casefold():
        raise ValidationError("У Карты Заклинаний поле kind должно быть «Заклинание».")
