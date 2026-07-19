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
)
from bot.keyboards.main_menu import cancel
from bot.middlewares.auth import AdminRule
from bot.services import book_slot_service, card_service
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
            slots = await book_slot_service.get_usage(session, character_id)
            text = formatters.character_card_holdings(ownerships, slots)
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
    await message.answer(
        "Введите ID анкеты получателя и количество копий. Например: 12 3. "
        "Если количество не указано, будет выдана 1 копия.",
        keyboard=cancel(),
    )


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
    await message.answer(
        "Введите ID карты и количество копий. Например: 25 3. "
        "По умолчанию — 1 копия.",
        keyboard=cancel(),
    )


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
    await message.answer(
        "Введите ID карты и количество списываемых свободных копий. "
        "Например: 25 2. По умолчанию — 1 копия.",
        keyboard=cancel(),
    )


@labeler.message(payload_contains={"cmd": "admin_character_special_grant"})
async def ask_special_grant(message: Message, **_: object) -> None:
    await _ask_numbered_change(
        message,
        AdminCardState.CHARACTER_GRANT_SPECIAL,
        "Введите номер Особого слота и количество. Например: 17 2.",
    )


@labeler.message(payload_contains={"cmd": "admin_character_special_revoke"})
async def ask_special_revoke(message: Message, **_: object) -> None:
    await _ask_numbered_change(
        message,
        AdminCardState.CHARACTER_REVOKE_SPECIAL,
        "Введите номер Особого слота и количество свободных копий для списания.",
    )


@labeler.message(payload_contains={"cmd": "admin_character_registry_grant"})
async def ask_registry_grant(message: Message, **_: object) -> None:
    await _ask_numbered_change(
        message,
        AdminCardState.CHARACTER_GRANT_REGISTRY,
        "Введите публичный ID реестровой карты (от 100) и количество. "
        "Например: 104 3.",
    )


@labeler.message(payload_contains={"cmd": "admin_character_registry_revoke"})
async def ask_registry_revoke(message: Message, **_: object) -> None:
    await _ask_numbered_change(
        message,
        AdminCardState.CHARACTER_REVOKE_REGISTRY,
        "Введите публичный ID реестровой карты (от 100) и количество "
        "списываемых свободных копий.",
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
        AdminCardState.ORDINARY_QUANTITY,
        card_type=CardType.ORDINARY.name,
        character_id=character_id,
    )
    await message.answer(
        "Сколько одинаковых копий Обычной карты добавить?",
        keyboard=cancel(),
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
        "Введите точное название Обычной карты и количество через «|». "
        "Например: Яблоко | 3. По умолчанию — 1 копия.",
        keyboard=cancel(),
    )


@labeler.message(state=AdminCardState.GRANT_CHARACTER)
async def give_selected_card(message: Message, **_: object) -> None:
    try:
        character_id, quantity = _parse_id_and_quantity(
            message.text, field="ID анкеты"
        )
        card_id = message.state_peer.payload["card_id"]
        async with get_session() as session:
            ownerships = await card_service.grant_card_copies(
                session, card_id, character_id, quantity=quantity
            )
            card = await cards_crud.get_by_id(session, card_id)
            character = await characters_crud.get_by_id(session, character_id)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Выдано {len(ownerships)} коп. карты #{card.id} · {card.name} персонажу "
        f"#{character.id} · {character.name}. ID копий: "
        f"{', '.join('#' + str(item.id) for item in ownerships)}.",
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
        name, quantity = _parse_name_and_quantity(message.text)
        async with get_session() as session:
            await card_service.revoke_ordinary_cards(
                session,
                character_id=character_id,
                name=name,
                quantity=quantity,
            )
            character = await characters_crud.get_by_id(session, character_id)
            ownerships = await cards_crud.list_character_ownerships(
                session, character_id
            )
            slots = await book_slot_service.get_usage(session, character_id)
            text = formatters.character_card_holdings(ownerships, slots)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Списано {quantity} коп. Обычной карты «{name}» у "
        f"#{character.id} · {character.name}.\n\n{text}",
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
    character_id = message.state_peer.payload["character_id"]
    try:
        number, quantity = _parse_non_negative_id_and_quantity(
            message.text, field="Номер карты"
        )
        async with get_session() as session:
            card = (
                await cards_crud.get_by_number(session, number)
                if special
                else await cards_crud.get_by_registry_number(session, number)
            )
            if card is None:
                pool = "Особого слота" if special else "реестровых карт"
                raise ValidationError(f"В пуле {pool} нет карты №{number}.")
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
            if revoke:
                await card_service.revoke_card_copies(
                    session, card.id, character_id, quantity=quantity
                )
            else:
                await card_service.grant_card_copies(
                    session, card.id, character_id, quantity=quantity
                )
            ownerships = await cards_crud.list_character_ownerships(
                session, character_id
            )
            slots = await book_slot_service.get_usage(session, character_id)
            holdings = formatters.character_card_holdings(ownerships, slots)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    action = "списано" if revoke else "выдано"
    await message.answer(
        f"Карта «{card.name}»: {action} {quantity} коп.\n\n{holdings}",
        keyboard=admin_character_cards_menu(character.id),
    )


async def _apply_character_card_change(message: Message, *, revoke: bool) -> None:
    try:
        card_id, quantity = _parse_id_and_quantity(
            message.text, field="ID карты"
        )
        character_id = message.state_peer.payload["character_id"]
        async with get_session() as session:
            card = await cards_crud.get_by_id(session, card_id)
            character = await characters_crud.get_by_id(session, character_id)
            if card is None:
                raise ValidationError("Карта не найдена.")
            if character is None:
                raise ValidationError("Анкета не найдена.")
            if revoke:
                await card_service.revoke_card_copies(
                    session, card_id, character_id, quantity=quantity
                )
            else:
                await card_service.grant_card_copies(
                    session, card_id, character_id, quantity=quantity
                )
            ownerships = await cards_crud.list_character_ownerships(
                session, character_id
            )
            slots = await book_slot_service.get_usage(session, character_id)
            text = formatters.character_card_holdings(ownerships, slots)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    action = "списано" if revoke else "выдано"
    await message.answer(
        f"Карта #{card.id} · {card.name}: {action} {quantity} коп.\n\n{text}",
        keyboard=admin_character_cards_menu(character.id),
    )


def _payload_id(message: Message, field: str) -> int:
    payload = message.get_payload_json() or {}
    return parse_positive_int(str(payload.get("id", "")), field=field)


def _parse_id_and_quantity(text: str, *, field: str) -> tuple[int, int]:
    raw_id, quantity = _split_quantity(text)
    return parse_positive_int(raw_id.removeprefix("#"), field=field), quantity


def _parse_non_negative_id_and_quantity(
    text: str, *, field: str
) -> tuple[int, int]:
    raw_id, quantity = _split_quantity(text)
    if not raw_id.removeprefix("#").isdigit():
        raise ValidationError(f"{field}: нужно целое число от 0.")
    return int(raw_id.removeprefix("#")), quantity


def _split_quantity(text: str) -> tuple[str, int]:
    parts = text.strip().split()
    if not parts or len(parts) > 2:
        raise ValidationError("Укажите идентификатор и, при необходимости, количество.")
    quantity = 1
    if len(parts) == 2:
        raw_quantity = parts[1].casefold()
        quantity = parse_positive_int(
            raw_quantity.removeprefix("x").removeprefix("х").removeprefix("×"),
            field="Количество карт",
        )
    return parts[0], quantity


def _parse_name_and_quantity(text: str) -> tuple[str, int]:
    name, separator, raw_quantity = text.rpartition("|")
    if not separator:
        name = text.strip()
        quantity = 1
    else:
        name = name.strip()
        quantity = parse_positive_int(raw_quantity, field="Количество карт")
    if not name:
        raise ValidationError("Укажите точное название карты.")
    return name, quantity
