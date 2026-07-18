from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import characters as characters_crud
from bot.database.engine import get_session
from bot.keyboards.admin_menu import (
    cancel_character_shakei_menu,
    selected_shakei_action_menu,
)
from bot.keyboards.main_menu import character_registry_detail_menu
from bot.middlewares.auth import AdminRule
from bot.services import shakei_service
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminShakeiState, clear_state, state_dispenser
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(payload_contains={"cmd": "admin_character_shakei"})
async def show_character_shakei(message: Message, **_: object) -> None:
    try:
        character_id = _payload_character_id(message)
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
            name, balance = character.name, character.shakei_balance
    except ServiceError as error:
        await message.answer(str(error))
        return

    await clear_state(message.peer_id)
    await message.answer(
        f"Шакеи персонажа #{character_id} · {name}\nБаланс: {balance}.\n\n"
        "Выберите действие:",
        keyboard=selected_shakei_action_menu(character_id),
    )


@labeler.message(payload_contains={"cmd": "admin_character_shakei_grant"})
async def start_grant(message: Message, **_: object) -> None:
    await _start_amount(message, is_grant=True)


@labeler.message(payload_contains={"cmd": "admin_character_shakei_deduct"})
async def start_deduct(message: Message, **_: object) -> None:
    await _start_amount(message, is_grant=False)


@labeler.message(state=AdminShakeiState.AMOUNT)
async def save_amount(message: Message, **_: object) -> None:
    try:
        amount = parse_positive_int(message.text, field="Сумма")
    except ServiceError as error:
        await message.answer(
            str(error),
            keyboard=cancel_character_shakei_menu(
                int(message.state_peer.payload["character_id"])
            ),
        )
        return

    await _apply(
        message,
        {**message.state_peer.payload, "amount": amount},
    )


async def _start_amount(message: Message, *, is_grant: bool) -> None:
    try:
        character_id = _payload_character_id(message)
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
            name, balance = character.name, character.shakei_balance
    except ServiceError as error:
        await message.answer(str(error))
        return

    await state_dispenser.set(
        message.peer_id,
        AdminShakeiState.AMOUNT,
        character_id=character_id,
        character_name=name,
        is_grant=is_grant,
    )
    action = "начислить" if is_grant else "списать"
    await message.answer(
        f"Персонаж: #{character_id} · {name}\nБаланс: {balance}.\n\n"
        f"Сколько Шакеев {action}? Пришлите только число.",
        keyboard=cancel_character_shakei_menu(character_id),
    )


async def _apply(message: Message, payload: dict[str, object]) -> None:
    character_id = int(payload["character_id"])
    amount = int(payload["amount"])
    is_grant = bool(payload["is_grant"])
    async with get_session() as session:
        try:
            if is_grant:
                await shakei_service.grant(
                    session,
                    character_id=character_id,
                    amount=amount,
                    admin_vk_id=message.from_id,
                    reason="",
                )
                action = "начислено"
            else:
                await shakei_service.deduct(
                    session,
                    character_id=character_id,
                    amount=amount,
                    admin_vk_id=message.from_id,
                    reason="",
                )
                action = "списано"
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
            name, balance = character.name, character.shakei_balance
        except ServiceError as error:
            await message.answer(
                str(error), keyboard=cancel_character_shakei_menu(character_id)
            )
            return

    await clear_state(message.peer_id)
    await message.answer(
        f"Персонажу #{character_id} · {name} {action} {amount} Шакеев. "
        f"Новый баланс: {balance}.",
        keyboard=character_registry_detail_menu(
            character_id, 0, is_admin=True
        ),
    )


def _payload_character_id(message: Message) -> int:
    payload = message.get_payload_json() or {}
    return parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
