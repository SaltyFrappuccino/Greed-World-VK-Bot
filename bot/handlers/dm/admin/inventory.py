from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.engine import get_session
from bot.database.models import CardType
from bot.keyboards.admin_menu import (
    admin_character_cards_menu,
    back_to_admin_cards,
    back_to_admin_characters,
    card_owners_menu,
    card_add_mode_menu,
)
from bot.keyboards.main_menu import cancel
from bot.middlewares.auth import AdminRule
from bot.services import card_service
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminCardState, clear_state, state_dispenser
from bot.utils import formatters
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(payload_contains={"cmd": "admin_character_cards"})
async def character_cards(message: Message, **_: object) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
            ownerships = await cards_crud.list_character_ownerships(
                session, character_id
            )
            text = formatters.character_card_holdings(ownerships)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Карты персонажа #{character.id} · {character.name}\n\n{text}",
        keyboard=admin_character_cards_menu(character.id),
    )


@labeler.message(payload_contains={"cmd": "admin_card_owners"})
async def card_owners(message: Message, **_: object) -> None:
    try:
        card_id = _payload_id(message, "ID карты")
        async with get_session() as session:
            card = await cards_crud.get_by_id(session, card_id)
            if card is None:
                raise ValidationError("Карта не найдена.")
            ownerships = await cards_crud.list_card_ownerships(session, card_id)
            text = formatters.card_owner_holdings(ownerships)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Владельцы карты #{card.id} · {card.name}\n\n{text}",
        keyboard=card_owners_menu(card.id),
    )


@labeler.message(payload_contains={"cmd": "admin_card_give"})
async def ask_card_recipient(message: Message, **_: object) -> None:
    try:
        card_id = _payload_id(message, "ID карты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return
    await state_dispenser.set(
        message.peer_id, AdminCardState.GRANT_CHARACTER, card_id=card_id
    )
    await message.answer("Введите ID анкеты получателя.", keyboard=cancel())


@labeler.message(payload_contains={"cmd": "admin_character_card_grant"})
async def ask_character_card(message: Message, **_: object) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.CHARACTER_GRANT_CARD,
        character_id=character_id,
    )
    await message.answer("Введите ID карты, которую нужно выдать.", keyboard=cancel())


@labeler.message(payload_contains={"cmd": "admin_character_card_revoke"})
async def ask_revoke_card(message: Message, **_: object) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.CHARACTER_REVOKE_CARD,
        character_id=character_id,
    )


@labeler.message(payload_contains={"cmd": "admin_character_special_grant"})
async def ask_special_grant(message: Message, **_: object) -> None:
    await _ask_numbered_change(
        message,
        AdminCardState.CHARACTER_GRANT_SPECIAL,
        "Введите номер Особого слота от 0 до 99.",
    )


@labeler.message(payload_contains={"cmd": "admin_character_special_revoke"})
async def ask_special_revoke(message: Message, **_: object) -> None:
    await _ask_numbered_change(
        message,
        AdminCardState.CHARACTER_REVOKE_SPECIAL,
        "Введите номер Особого слота, который нужно забрать.",
    )


@labeler.message(payload_contains={"cmd": "admin_character_registry_grant"})
async def ask_registry_grant(message: Message, **_: object) -> None:
    await _ask_numbered_change(
        message,
        AdminCardState.CHARACTER_GRANT_REGISTRY,
        "Введите общий номер Заклинания или Контурной карты, начиная с 0.",
    )


@labeler.message(payload_contains={"cmd": "admin_character_registry_revoke"})
async def ask_registry_revoke(message: Message, **_: object) -> None:
    await _ask_numbered_change(
        message,
        AdminCardState.CHARACTER_REVOKE_REGISTRY,
        "Введите общий номер Заклинания или Контурной карты, которую нужно забрать.",
    )


@labeler.message(payload_contains={"cmd": "admin_character_ordinary_add"})
async def add_ordinary_card(message: Message, **_: object) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.ADD_MODE,
        card_type=CardType.ORDINARY.name,
        character_id=character_id,
    )
    await message.answer(
        "Как добавить Обычную карту этому персонажу?",
        keyboard=card_add_mode_menu(),
    )


@labeler.message(payload_contains={"cmd": "admin_character_ordinary_revoke"})
async def ask_ordinary_revoke(message: Message, **_: object) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.CHARACTER_REVOKE_ORDINARY,
        character_id=character_id,
    )
    await message.answer(
        "Введите точное название Обычной карты. Будет забрана одна свободная копия.",
        keyboard=cancel(),
    )


@labeler.message(state=AdminCardState.GRANT_CHARACTER)
async def give_selected_card(message: Message, **_: object) -> None:
    try:
        character_id = parse_positive_int(message.text, field="ID анкеты")
        card_id = message.state_peer.payload["card_id"]
        async with get_session() as session:
            ownership = await card_service.grant_card(session, card_id, character_id)
            card = await cards_crud.get_by_id(session, card_id)
            character = await characters_crud.get_by_id(session, character_id)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Выдана копия #{ownership.id} карты #{card.id} · {card.name} персонажу "
        f"#{character.id} · {character.name}.",
        keyboard=card_owners_menu(card.id),
    )


@labeler.message(state=AdminCardState.CHARACTER_GRANT_CARD)
async def give_card_to_selected_character(message: Message, **_: object) -> None:
    await _apply_character_card_change(message, revoke=False)


@labeler.message(state=AdminCardState.CHARACTER_REVOKE_CARD)
async def revoke_card_from_selected_character(message: Message, **_: object) -> None:
    await _apply_character_card_change(message, revoke=True)


@labeler.message(state=AdminCardState.CHARACTER_GRANT_SPECIAL)
async def grant_special(message: Message, **_: object) -> None:
    await _apply_numbered_card_change(message, special=True, revoke=False)


@labeler.message(state=AdminCardState.CHARACTER_REVOKE_SPECIAL)
async def revoke_special(message: Message, **_: object) -> None:
    await _apply_numbered_card_change(message, special=True, revoke=True)


@labeler.message(state=AdminCardState.CHARACTER_GRANT_REGISTRY)
async def grant_registry_card(message: Message, **_: object) -> None:
    await _apply_numbered_card_change(message, special=False, revoke=False)


@labeler.message(state=AdminCardState.CHARACTER_REVOKE_REGISTRY)
async def revoke_registry_card(message: Message, **_: object) -> None:
    await _apply_numbered_card_change(message, special=False, revoke=True)


@labeler.message(state=AdminCardState.CHARACTER_REVOKE_ORDINARY)
async def revoke_ordinary_card(message: Message, **_: object) -> None:
    character_id = message.state_peer.payload["character_id"]
    try:
        async with get_session() as session:
            await card_service.revoke_ordinary_card(
                session, character_id=character_id, name=message.text
            )
            character = await characters_crud.get_by_id(session, character_id)
            ownerships = await cards_crud.list_character_ownerships(
                session, character_id
            )
            text = formatters.character_card_holdings(ownerships)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Обычная карта забрана у #{character.id} · {character.name}.\n\n{text}",
        keyboard=admin_character_cards_menu(character.id),
    )


async def _ask_numbered_change(
    message: Message, state_name: str, prompt: str
) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id, state_name, character_id=character_id
    )
    await message.answer(prompt, keyboard=cancel())


async def _apply_numbered_card_change(
    message: Message, *, special: bool, revoke: bool
) -> None:
    text_number = message.text.strip()
    if not text_number.isdigit():
        await message.answer("Номер должен быть целым числом от 0.", keyboard=cancel())
        return
    number = int(text_number)
    character_id = message.state_peer.payload["character_id"]
    try:
        async with get_session() as session:
            card = (
                await cards_crud.get_by_number(session, number)
                if special
                else await cards_crud.get_by_registry_number(session, number)
            )
            if card is None:
                pool = "Особого слота" if special else "Заклинаний/Контурных карт"
                raise ValidationError(f"В пуле {pool} нет карты №{number}.")
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
            if revoke:
                await card_service.revoke_card(session, card.id, character_id)
            else:
                await card_service.grant_card(session, card.id, character_id)
            ownerships = await cards_crud.list_character_ownerships(
                session, character_id
            )
            holdings = formatters.character_card_holdings(ownerships)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    action = "забрана" if revoke else "выдана"
    await message.answer(
        f"Карта «{card.name}» {action}.\n\n{holdings}",
        keyboard=admin_character_cards_menu(character.id),
    )


async def _apply_character_card_change(message: Message, *, revoke: bool) -> None:
    try:
        card_id = parse_positive_int(message.text, field="ID карты")
        character_id = message.state_peer.payload["character_id"]
        async with get_session() as session:
            card = await cards_crud.get_by_id(session, card_id)
            character = await characters_crud.get_by_id(session, character_id)
            if card is None:
                raise ValidationError("Карта не найдена.")
            if character is None:
                raise ValidationError("Анкета не найдена.")
            if revoke:
                await card_service.revoke_card(session, card_id, character_id)
            else:
                await card_service.grant_card(session, card_id, character_id)
            ownerships = await cards_crud.list_character_ownerships(
                session, character_id
            )
            text = formatters.character_card_holdings(ownerships)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    action = "забрана" if revoke else "выдана"
    await message.answer(
        f"Карта #{card.id} · {card.name} {action}.\n\n{text}",
        keyboard=admin_character_cards_menu(character.id),
    )


def _payload_id(message: Message, field: str) -> int:
    payload = message.get_payload_json() or {}
    return parse_positive_int(str(payload.get("id", "")), field=field)
