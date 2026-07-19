from vkbottle.bot import Message

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.engine import get_session
from bot.database.models import CardType
from bot.keyboards.admin_menu import (
    back_to_admin_cards,
    admin_character_cards_menu,
    ai_collect_menu,
    ai_confirm_menu,
    card_add_mode_menu,
    card_rarity_menu,
    card_type_menu,
    confirm_menu,
    contour_subtype_menu,
    skip_card_field_menu,
    special_card_limit_menu,
)
from bot.keyboards.main_menu import cancel, card_registry_detail_menu
from bot.middlewares.auth import AdminRule
from bot.services import ai_service, card_service
from bot.services.card_template_service import (
    CONTOUR_SUBTYPES,
    parse_card_template,
    parse_card_type,
    template_for,
)
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminCardState, clear_state, state_dispenser
from bot.utils import formatters
from bot.utils.messages import answer_long
from bot.utils.validators import (
    parse_optional_limit,
    parse_optional_slot_number,
    parse_positive_int,
    parse_rarity,
)
from bot.handlers.dm.admin.card_handlers.routing import labeler


EDIT_HINT = """Пришлите правку одной строкой:

поле = значение

Поля: название, редкость, лимит, номер, описание, использование, подтип контура.
Пример: лимит = 5"""

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

@labeler.message(payload={"cmd": "admin_card_edit"})
async def start_edit(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCardState.EDIT_PICK)
    await message.answer("Какую карту правим? Название или номер слота.", keyboard=cancel())


@labeler.message(payload_contains={"cmd": "admin_card_edit_select"})
async def select_edit_target(message: Message, **_: object) -> None:
    try:
        card_id = _payload_id(message)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return
    await _open_card_editor(message, card_id)


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
    await message.answer(
        f"Обновлено.\n\n{text}",
        keyboard=card_registry_detail_menu(
            card.id, 0, card_type=card.card_type, is_admin=True
        ),
    )


@labeler.message(payload={"cmd": "admin_card_delete"})
async def start_delete(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCardState.DELETE_PICK)
    await message.answer("Какую карту удаляем? Название или номер слота.", keyboard=cancel())


@labeler.message(payload_contains={"cmd": "admin_card_delete_select"})
async def select_delete_target(message: Message, **_: object) -> None:
    try:
        card_id = _payload_id(message)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return
    await _show_delete_confirmation(message, card_id)


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
        f"\n\n⚠️ Живых копий карты: {live_copies} — свободные владения тоже удалятся."
        if live_copies
        else ""
    )
    await message.answer(
        f"Удалить карту «{name}»?{warning}",
        keyboard=confirm_menu(
            "admin_card_delete",
            card_id,
            cancel_payload={
                "cmd": "card_registry_view",
                "id": card_id,
                "page": 0,
                "type": card.card_type.name,
            },
        ),
    )


@labeler.message(payload_contains={"cmd": "admin_card_delete_confirm"})
async def confirm_delete(message: Message, **_: object) -> None:
    card_id = (message.get_payload_json() or {}).get("id")

    async with get_session() as session:
        try:
            name = await card_service.delete_card(session, int(card_id))
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_admin_cards())
            return

    await message.answer(
        f"Карта «{name}» удалена из реестра.", keyboard=back_to_admin_cards()
    )


async def _open_card_editor(message: Message, card_id: int) -> None:
    async with get_session() as session:
        card = await cards_crud.get_by_id(session, card_id)
        if card is None:
            await message.answer("Карта не найдена.", keyboard=back_to_admin_cards())
            return
        live_copies = await cards_crud.count_owners(session, card.id)
        text = formatters.card_full(card, live_copies)

    await state_dispenser.set(
        message.peer_id, AdminCardState.EDIT_VALUE, card_id=card_id
    )
    await message.answer(f"{text}\n\n{EDIT_HINT}", keyboard=cancel())


async def _show_delete_confirmation(message: Message, card_id: int) -> None:
    async with get_session() as session:
        card = await cards_crud.get_by_id(session, card_id)
        if card is None:
            await message.answer("Карта не найдена.", keyboard=back_to_admin_cards())
            return
        live_copies = await cards_crud.count_owners(session, card.id)
        name = card.name

    await clear_state(message.peer_id)
    warning = (
        f"\n\n⚠️ Живых копий карты: {live_copies} — свободные владения тоже удалятся."
        if live_copies
        else ""
    )
    await message.answer(
        f"Точно удалить карту «{name}»? Отменить это действие будет нельзя.{warning}",
        keyboard=confirm_menu(
            "admin_card_delete",
            card_id,
            cancel_payload={
                "cmd": "card_registry_view",
                "id": card_id,
                "page": 0,
                "type": card.card_type.name,
            },
        ),
    )


def _payload_id(message: Message) -> int:
    value = (message.get_payload_json() or {}).get("id")
    try:
        card_id = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Некорректный ID карты.") from None
    if card_id <= 0:
        raise ValidationError("Некорректный ID карты.")
    return card_id
