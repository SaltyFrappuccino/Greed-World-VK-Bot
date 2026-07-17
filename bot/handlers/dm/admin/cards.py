from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.engine import get_session
from bot.keyboards.admin_menu import back_to_admin, card_type_menu, confirm_menu
from bot.keyboards.main_menu import cancel
from bot.middlewares.auth import AdminRule
from bot.services import card_service
from bot.services.card_template_service import (
    parse_card_template,
    parse_card_type,
    template_for,
)
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminCardState, clear_state, state_dispenser
from bot.utils import formatters
from bot.utils.validators import parse_optional_limit, parse_optional_slot_number, parse_rarity

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True

EDIT_HINT = """Пришлите правку одной строкой:

поле = значение

Поля: название, редкость, лимит, номер, описание, использование, подтип контура.
Пример: лимит = 5"""

# Ввод админа -> поле модели.
EDIT_FIELDS = {
    "название": "name",
    "вид": "kind",
    "подтип контура": "kind",
    "редкость": "rarity",
    "лимит": "transform_limit",
    "номер": "number",
    "описание": "description",
    "использование": "usage",
}


@labeler.message(payload={"cmd": "admin_card_add"})
async def start_add(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCardState.TYPE)
    await message.answer("Сначала выберите тип карты:", keyboard=card_type_menu())


@labeler.message(payload_contains={"cmd": "admin_card_type"})
async def choose_card_type(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    try:
        card_type = parse_card_type(str(payload.get("type", "")))
    except ServiceError as error:
        await message.answer(str(error), keyboard=card_type_menu())
        return

    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD, card_type=card_type.name
    )
    await message.answer(template_for(card_type), keyboard=cancel())


@labeler.message(state=AdminCardState.ADD)
async def do_add(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            card_type = parse_card_type(message.state_peer.payload["card_type"])
            draft = parse_card_template(card_type, message.text)
            card = await card_service.create_card(
                session,
                name=draft.name,
                card_type=draft.card_type,
                kind=draft.kind,
                rarity=draft.rarity,
                transform_limit=draft.transform_limit,
                number=draft.number,
                description=draft.description,
                usage=draft.usage,
                admin_vk_id=message.from_id,
            )
            text = formatters.card_full(card, live_copies=0)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(f"Карта добавлена.\n\n{text}", keyboard=back_to_admin())


@labeler.message(payload={"cmd": "admin_card_edit"})
async def start_edit(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCardState.EDIT_PICK)
    await message.answer("Какую карту правим? Название или номер слота.", keyboard=cancel())


@labeler.message(state=AdminCardState.EDIT_PICK)
async def pick_edit_target(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            card = await card_service.find_card(session, message.text)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

        live_copies = await cards_crud.count_owners(session, card.id)
        card_id, text = card.id, formatters.card_full(card, live_copies)

    await state_dispenser.set(message.peer_id, AdminCardState.EDIT_VALUE, card_id=card_id)
    await message.answer(f"{text}\n\n{EDIT_HINT}", keyboard=cancel())


@labeler.message(state=AdminCardState.EDIT_VALUE)
async def do_edit(message: Message, **_: object) -> None:
    card_id = message.state_peer.payload["card_id"]
    field_text, sep, value_text = message.text.partition("=")
    if not sep:
        await message.answer("Формат: поле = значение", keyboard=cancel())
        return

    field_key = field_text.strip().lower()
    value_text = value_text.strip()

    async with get_session() as session:
        try:
            if field_key not in EDIT_FIELDS:
                raise ValidationError(f"Неизвестное поле. Доступны: {', '.join(EDIT_FIELDS)}.")

            field = EDIT_FIELDS[field_key]
            value: object = value_text
            if field == "rarity":
                value = parse_rarity(value_text)
            elif field == "transform_limit":
                value = parse_optional_limit(value_text)
            elif field == "number":
                value = parse_optional_slot_number(value_text)

            card = await card_service.update_card(session, card_id, **{field: value})
            live_copies = await cards_crud.count_owners(session, card.id)
            text = formatters.card_full(card, live_copies)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(f"Обновлено.\n\n{text}", keyboard=back_to_admin())


@labeler.message(payload={"cmd": "admin_card_delete"})
async def start_delete(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCardState.DELETE_PICK)
    await message.answer("Какую карту удаляем? Название или номер слота.", keyboard=cancel())


@labeler.message(state=AdminCardState.DELETE_PICK)
async def pick_delete_target(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            card = await card_service.find_card(session, message.text)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

        live_copies = await cards_crud.count_owners(session, card.id)
        card_id, name = card.id, card.name

    await clear_state(message.peer_id)
    warning = (
        f"\n\n⚠️ Карта на руках у {live_copies} персонажей - владения тоже удалятся."
        if live_copies
        else ""
    )
    await message.answer(
        f"Удалить карту «{name}»?{warning}",
        keyboard=confirm_menu("admin_card_delete", card_id),
    )


@labeler.message(payload_contains={"cmd": "admin_card_delete_confirm"})
async def confirm_delete(message: Message, **_: object) -> None:
    card_id = (message.get_payload_json() or {}).get("id")

    async with get_session() as session:
        try:
            name = await card_service.delete_card(session, int(card_id))
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_admin())
            return

    await message.answer(f"Карта «{name}» удалена из реестра.", keyboard=back_to_admin())


@labeler.message(text="?!выдать <card_name> <character_name>")
async def grant_card(message: Message, card_name: str, character_name: str, **_: object) -> None:
    """Выдача копии карты - здесь и проверяется лимит преобразований."""
    from bot.services import character_service

    async with get_session() as session:
        try:
            card = await card_service.find_card(session, card_name)
            character = await character_service.find_character(session, character_name)
            await card_service.grant_card(session, card.id, character.id)
            live_copies = await cards_crud.count_owners(session, card.id)
            limit_text = formatters.format_limit(card, live_copies)
            names = (card.name, character.name)
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_admin())
            return

    await message.answer(
        f"Карта «{names[0]}» выдана персонажу {names[1]}.\nПреобразования: {limit_text}",
        keyboard=back_to_admin(),
    )


@labeler.message(text="?!забрать <card_name> <character_name>")
async def revoke_card(message: Message, card_name: str, character_name: str, **_: object) -> None:
    from bot.services import character_service

    async with get_session() as session:
        try:
            card = await card_service.find_card(session, card_name)
            character = await character_service.find_character(session, character_name)
            await card_service.revoke_card(session, card.id, character.id)
            names = (card.name, character.name)
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_admin())
            return

    await message.answer(
        f"Карта «{names[0]}» забрана у персонажа {names[1]} - преобразование освободилось.",
        keyboard=back_to_admin(),
    )
