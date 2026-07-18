from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import contours as contours_crud
from bot.database.engine import get_session
from bot.keyboards.admin_menu import (
    admin_character_edit_menu,
    back_to_admin_characters,
    confirm_menu,
)
from bot.keyboards.main_menu import cancel, character_select_menu
from bot.middlewares.auth import AdminRule
from bot.services import character_service
from bot.services.character_template_service import CHARACTER_TEMPLATE, parse_character_template
from bot.services.vk_service import resolve_user_id
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminCharacterState, AdminStatsState, clear_state, state_dispenser
from bot.utils.validators import parse_int, parse_positive_int, parse_rarity

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True

_ADMIN_EDITABLE_FIELDS = {
    "name": "имя",
    "age": "возраст",
    "gender": "пол",
    "appearance": "внешность",
    "personality": "характер",
    "biography": "биографию",
    "skills": "навыки",
    "additional": "дополнительные сведения",
    **character_service.STAT_FIELDS,
    "overall_rating": "рейтинг",
    "vk_id": "владельца VK",
}


@labeler.message(payload={"cmd": "admin_character_add"})
async def start_character_add(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCharacterState.OWNER)
    await message.answer(
        "Кому принадлежит анкета? Пришлите числовой VK ID, упоминание "
        "или любую ссылку на профиль, например vk.ru/sword_saint.",
        keyboard=cancel(),
    )


@labeler.message(state=AdminCharacterState.OWNER)
async def pick_character_owner(message: Message, **_: object) -> None:
    try:
        vk_id = await resolve_user_id(message.ctx_api, message.text)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return

    await state_dispenser.set(
        message.peer_id, AdminCharacterState.TEMPLATE, owner_vk_id=vk_id
    )
    await message.answer(CHARACTER_TEMPLATE, keyboard=cancel())


@labeler.message(state=AdminCharacterState.TEMPLATE)
async def save_character(message: Message, **_: object) -> None:
    owner_vk_id = message.state_peer.payload["owner_vk_id"]
    async with get_session() as session:
        try:
            fields = parse_character_template(message.text)
            name = str(fields.pop("name"))
            character = await character_service.create_character(
                session, vk_id=owner_vk_id, name=name, **fields
            )
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(
        f"Анкета «{character.name}» добавлена владельцу https://vk.ru/id{owner_vk_id}.",
        keyboard=back_to_admin_characters(),
    )


@labeler.message(payload={"cmd": "admin_character_edit"})
async def start_character_edit(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCharacterState.EDIT_PICK)
    await message.answer(
        "Какую анкету редактируем? Пришлите:\n"
        "• имя персонажа;\n"
        "• #ID анкеты, например #12;\n"
        "• VK ID, упоминание или ссылку владельца.\n\n"
        "Если у владельца несколько персонажей, я покажу выбор.",
        keyboard=cancel(),
    )


@labeler.message(payload_contains={"cmd": "admin_character_edit_select"})
async def select_character_edit(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await _show_character_editor(message, character_id)


@labeler.message(payload_contains={"cmd": "admin_character_delete_select"})
async def select_character_delete(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(
            str(payload.get("id", "")), field="ID анкеты"
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await _show_character_delete_confirmation(message, character_id)


@labeler.message(payload_contains={"cmd": "admin_character_delete_confirm"})
async def confirm_character_delete(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(
            str(payload.get("id", "")), field="ID анкеты"
        )
        async with get_session() as session:
            name = await character_service.delete_character(session, character_id)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Анкета #{character_id} · {name} удалена.",
        keyboard=back_to_admin_characters(),
    )


@labeler.message(payload_contains={"cmd": "admin_character_edit_field"})
async def select_character_field(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    field = str(payload.get("field", ""))
    if field not in _ADMIN_EDITABLE_FIELDS:
        await message.answer(
            "Это поле редактировать нельзя.", keyboard=back_to_admin_characters()
        )
        return
    try:
        character_id = parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return

    async with get_session() as session:
        character = await characters_crud.get_by_id(session, character_id)
        if character is None:
            await message.answer(
                "Анкета не найдена.", keyboard=back_to_admin_characters()
            )
            return
        current = getattr(character, field)
        if hasattr(current, "value"):
            current = current.value

    await state_dispenser.set(
        message.peer_id,
        AdminCharacterState.EDIT_VALUE,
        character_id=character_id,
        field=field,
    )
    hint = " Для очистки пришлите «-»." if field in {
        "age", "gender", "appearance", "personality", "biography", "skills", "additional"
    } else ""
    await message.answer(
        f"Персонаж #{character.id} · {character.name}\n"
        f"Поле: {_ADMIN_EDITABLE_FIELDS[field]}\n"
        f"Сейчас: {str(current)[:1000] or '—'}\n\n"
        f"Пришлите новое значение.{hint}",
        keyboard=cancel(),
    )


@labeler.message(state=AdminCharacterState.EDIT_PICK)
async def pick_character_edit(message: Message, **_: object) -> None:
    query = message.text.strip()
    async with get_session() as session:
        try:
            if query.startswith("#"):
                character_id = parse_positive_int(query[1:], field="ID анкеты")
                character = await characters_crud.get_by_id(session, character_id)
                matches = [character] if character is not None else []
            elif _looks_like_vk_reference(query):
                owner_vk_id = await resolve_user_id(message.ctx_api, query)
                matches = await character_service.list_by_vk_id(session, owner_vk_id)
            else:
                exact = await characters_crud.get_by_name(session, query)
                matches = [exact] if exact is not None else await characters_crud.search_by_name(
                    session, query, limit=18
                )
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    if not matches:
        await message.answer("Подходящих анкет не найдено.", keyboard=cancel())
        return
    if len(matches) > 1:
        await message.answer(
            "Найдено несколько персонажей. Выберите конкретную анкету:",
            keyboard=character_select_menu("admin_character_edit_select", matches),
        )
        return
    await _show_character_editor(message, matches[0].id)


@labeler.message(state=AdminCharacterState.EDIT_VALUE)
async def save_character_field(message: Message, **_: object) -> None:
    payload = message.state_peer.payload
    character_id = payload["character_id"]
    field = payload["field"]
    value_text = message.text.strip()

    async with get_session() as session:
        try:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
            if field == "name":
                await character_service.rename_character(session, character, value_text)
            elif field == "vk_id":
                owner_vk_id = await resolve_user_id(message.ctx_api, value_text)
                await character_service.change_owner(session, character, owner_vk_id)
            elif field == "age":
                age = None if value_text == "-" else parse_positive_int(value_text, field="Возраст")
                await character_service.update_profile(session, character, age=age)
            elif field == "overall_rating":
                await character_service.set_rating(session, character.id, parse_rarity(value_text))
            elif field in character_service.STAT_FIELDS:
                value = parse_int(value_text, field="Значение стата")
                await character_service.set_stat(session, character.id, field, value)
            else:
                value = "" if value_text == "-" else value_text
                await character_service.update_profile(session, character, **{field: value})
            name = character.name
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(
        f"Анкета #{character_id} · {name}: поле «{_ADMIN_EDITABLE_FIELDS[field]}» обновлено.",
        keyboard=admin_character_edit_menu(character_id),
    )


async def _show_character_editor(message: Message, character_id: int) -> None:
    async with get_session() as session:
        character = await characters_crud.get_by_id(session, character_id)
        if character is None:
            await message.answer(
                "Анкета не найдена.", keyboard=back_to_admin_characters()
            )
            return
        name = character.name
        owner_vk_id = character.vk_id
    await clear_state(message.peer_id)
    await message.answer(
        f"Редактирование анкеты #{character_id}\n"
            f"Персонаж: {name}\nВладелец: https://vk.ru/id{owner_vk_id}\n\n"
        "Выберите поле:",
        keyboard=admin_character_edit_menu(character_id),
    )


async def _show_character_delete_confirmation(
    message: Message, character_id: int
) -> None:
    async with get_session() as session:
        character = await characters_crud.get_by_id(session, character_id)
        if character is None:
            await message.answer(
                "Анкета не найдена.", keyboard=back_to_admin_characters()
            )
            return
        cards = await cards_crud.list_character_cards(session, character.id)
        contours = await contours_crud.list_for_character(session, character.id)
        name = character.name
        owner_vk_id = character.vk_id

    await clear_state(message.peer_id)
    warning = (
        f"\n\nБудут удалены привязки карт: {len(cards)}; Контуры: {len(contours)}."
        if cards or contours
        else ""
    )
    await message.answer(
        f"Точно удалить анкету #{character_id} · {name} "
        f"(https://vk.ru/id{owner_vk_id})? "
        f"Отменить это действие будет нельзя.{warning}",
        keyboard=confirm_menu(
            "admin_character_delete",
            character_id,
            cancel_payload={
                "cmd": "character_registry_view",
                "id": character_id,
                "page": 0,
            },
        ),
    )


def _looks_like_vk_reference(query: str) -> bool:
    lowered = query.casefold()
    return query.isdigit() or lowered.startswith("[id") or "vk.com/" in lowered or "vk.ru/" in lowered


@labeler.message(payload={"cmd": "admin_stats"})
async def start_adjustment(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminStatsState.INPUT)
    await message.answer(
        "Пришлите одной строкой:\n\n"
        "имя персонажа | показатель | значение\n\n"
        "Показатели: стрессоустойчивость, речевой аппарат, чуйка, хребет, "
        "воля, нюх, рейтинг. Статы - от 1 до 5, рейтинг - от H до SS.\n\n"
        "Пример: Ава | чуйка | 5",
        keyboard=cancel(),
    )


@labeler.message(state=AdminStatsState.INPUT)
async def apply_adjustment(message: Message, **_: object) -> None:
    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 3:
        await message.answer(
            "Формат: имя персонажа | показатель | значение", keyboard=cancel()
        )
        return

    character_name, indicator, value_text = parts
    async with get_session() as session:
        try:
            character = await character_service.find_character(session, character_name)
            if indicator.lower() == "рейтинг":
                rating = parse_rarity(value_text)
                await character_service.set_rating(session, character.id, rating)
                result = f"рейтинг {rating.value}"
            else:
                value = parse_int(value_text, field="Значение стата")
                field = character_service.resolve_stat(indicator)
                await character_service.set_stat(session, character.id, field, value)
                result = f"{character_service.STAT_FIELDS[field]} {value}"
            name = character.name
        except (ServiceError, ValidationError) as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(
        f"У персонажа {name} установлено: {result}.",
        keyboard=back_to_admin_characters(),
    )
