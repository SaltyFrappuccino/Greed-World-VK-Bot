from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import characters as characters_crud
from bot.database.models import Character, Rarity
from bot.services.errors import NotFoundError, ValidationError

STAT_FIELDS: dict[str, str] = {
    "stress_resistance": "стрессоустойчивость",
    "speech": "речевой аппарат",
    "intuition": "чуйка",
    "spine": "хребет",
    "will": "воля",
    "scent": "нюх",
}

STAT_ALIASES: dict[str, str] = {title: field for field, title in STAT_FIELDS.items()}

STAT_MIN = 1
STAT_MAX = 5


def resolve_stat(name: str) -> str:
    """Название стата из ввода -> поле модели."""
    key = name.strip().lower()
    if key in STAT_FIELDS:
        return key
    if key in STAT_ALIASES:
        return STAT_ALIASES[key]
    known = ", ".join(STAT_FIELDS.values())
    raise ValidationError(f"Неизвестный стат «{name}». Доступны: {known}.")


def validate_stat_value(value: int) -> int:
    if not STAT_MIN <= value <= STAT_MAX:
        raise ValidationError(f"Значение стата должно быть от {STAT_MIN} до {STAT_MAX}.")
    return value


async def list_by_vk_id(session: AsyncSession, vk_id: int) -> list[Character]:
    return await characters_crud.list_by_vk_id(session, vk_id)


async def list_registry(
    session: AsyncSession,
    *,
    offset: int,
    limit: int,
    include_unapproved: bool = False,
) -> list[Character]:
    return await characters_crud.list_characters(
        session,
        offset=offset,
        limit=limit,
        approved_only=not include_unapproved,
    )


async def count_registry(
    session: AsyncSession, *, include_unapproved: bool = False
) -> int:
    return await characters_crud.count_characters(
        session, approved_only=not include_unapproved
    )


async def require_single_by_vk_id(session: AsyncSession, vk_id: int) -> Character:
    characters = await list_by_vk_id(session, vk_id)
    if not characters:
        raise NotFoundError("У этого пользователя нет анкет.")
    if len(characters) > 1:
        names = ", ".join(
            f"#{character.id} · {character.name}" for character in characters
        )
        raise ValidationError(
            f"У пользователя несколько анкет: {names}. Укажите ID анкеты."
        )
    return characters[0]


async def require_owned(
    session: AsyncSession, *, character_id: int, vk_id: int
) -> Character:
    character = await characters_crud.get_owned(session, character_id, vk_id)
    if character is None:
        raise NotFoundError("Анкета не найдена или принадлежит другому пользователю.")
    return character


async def find_character(session: AsyncSession, query: str) -> Character:
    """Найти персонажа по ID или имени: сначала точное совпадение, потом подстрока."""
    query = query.strip()
    if not query:
        raise ValidationError("Укажите ID или имя персонажа.")

    id_text = query.removeprefix("#")
    if id_text.isdigit():
        by_id = await characters_crud.get_by_id(session, int(id_text))
        if by_id is None:
            raise NotFoundError(f"Анкета с ID #{id_text} не найдена.")
        return by_id

    exact = await characters_crud.get_by_name(session, query)
    if exact is not None:
        return exact

    matches = await characters_crud.search_by_name(session, query, limit=6)
    if not matches:
        raise NotFoundError(f"Персонаж «{query}» не найден.")
    if len(matches) > 1:
        names = ", ".join(character.name for character in matches)
        raise ValidationError(f"Подходит несколько персонажей: {names}. Уточните имя.")
    return matches[0]


async def create_character(session: AsyncSession, *, vk_id: int, name: str, **fields: object) -> Character:
    if not name.strip():
        raise ValidationError("Имя персонажа не может быть пустым.")
    if await characters_crud.get_by_name(session, name) is not None:
        raise ValidationError(f"Персонаж с именем «{name.strip()}» уже есть.")

    return await characters_crud.create(session, vk_id=vk_id, name=name, **fields)


async def rename_character(
    session: AsyncSession, character: Character, name: str
) -> Character:
    name = name.strip()
    if not name:
        raise ValidationError("Имя персонажа не может быть пустым.")
    existing = await characters_crud.get_by_name(session, name)
    if existing is not None and existing.id != character.id:
        raise ValidationError(f"Персонаж с именем «{name}» уже есть.")
    return await characters_crud.update(session, character, name=name)


async def change_owner(
    session: AsyncSession, character: Character, vk_id: int
) -> Character:
    if vk_id <= 0:
        raise ValidationError("VK ID владельца должен быть больше нуля.")
    return await characters_crud.update(session, character, vk_id=vk_id)


async def delete_character(session: AsyncSession, character_id: int) -> str:
    from bot.services import character_art_service
    from bot.services import profile_card_service

    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    name = character.name
    await character_art_service.queue_character_files_for_delete(
        session, character_id
    )
    await profile_card_service.queue_character_file_for_delete(
        session, character_id
    )
    await characters_crud.delete(session, character)
    return name


async def update_profile(session: AsyncSession, character: Character, **fields: object) -> Character:
    """Правка описательных полей анкеты. Статы и баланс сюда не пускаем."""
    forbidden = set(fields) & (set(STAT_FIELDS) | {"shakei_balance", "overall_rating", "is_approved"})
    if forbidden:
        raise ValidationError(f"Эти поля меняет только админ: {', '.join(sorted(forbidden))}.")
    return await characters_crud.update(session, character, **fields)


async def set_pending_stat(
    session: AsyncSession, character: Character, stat: str, value: int
) -> Character:
    """Игрок расставляет статы сам, но только пока анкета ждёт подтверждения."""
    if character.is_approved:
        raise ValidationError("После подтверждения статы корректирует администратор.")
    field = resolve_stat(stat)
    validate_stat_value(value)
    return await characters_crud.update(session, character, **{field: value})


async def set_stat(session: AsyncSession, character_id: int, stat: str, value: int) -> Character:
    field = resolve_stat(stat)
    validate_stat_value(value)

    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")

    return await characters_crud.update(session, character, **{field: value})


async def set_rating(session: AsyncSession, character_id: int, rating: Rarity) -> Character:
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")

    return await characters_crud.update(session, character, overall_rating=rating)


async def approve(session: AsyncSession, character_id: int) -> Character:
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")
    if character.is_approved:
        raise ValidationError(f"Анкета {character.name} уже подтверждена.")
    return await characters_crud.update(session, character, is_approved=True)


async def list_pending(session: AsyncSession, limit: int = 20) -> list[Character]:
    return await characters_crud.list_pending(session, limit=limit)
