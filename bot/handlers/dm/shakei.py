from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.main_menu import cancel, character_select_menu, main_menu
from bot.services import character_service, shakei_service
from bot.services.errors import ServiceError
from bot.states import TransferState, clear_state, state_dispenser
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True


@labeler.message(payload={"cmd": "transfer"})
async def start_transfer(message: Message, **_: object) -> None:
    async with get_session() as session:
        characters = await character_service.list_by_vk_id(session, message.from_id)
        if not characters:
            await message.answer(
                "У вас нет анкет. Их добавляет администратор.",
                keyboard=main_menu(False),
            )
            return
        if len(characters) > 1:
            await message.answer(
                "От имени какого персонажа переводим?",
                keyboard=character_select_menu("transfer_sender", characters),
            )
            return
        character = characters[0]

    await _ask_recipient(message, character.id, character.name, character.shakei_balance)


@labeler.message(payload_contains={"cmd": "transfer_sender"})
async def pick_sender(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = int(payload.get("id"))
    except (TypeError, ValueError):
        await message.answer("Некорректная анкета.", keyboard=main_menu(False))
        return

    async with get_session() as session:
        try:
            character = await character_service.require_owned(
                session, character_id=character_id, vk_id=message.from_id
            )
        except ServiceError as error:
            await message.answer(str(error), keyboard=main_menu(False))
            return

    await _ask_recipient(
        message, character.id, character.name, character.shakei_balance
    )


async def _ask_recipient(
    message: Message, sender_id: int, sender_name: str, balance: int
) -> None:
    await state_dispenser.set(
        message.peer_id,
        TransferState.RECIPIENT,
        sender_id=sender_id,
        sender_name=sender_name,
    )

    await message.answer(
        f"Персонаж: {sender_name}. Баланс: {balance} Шакеев.\n"
        "Кому переводим? Пришлите имя персонажа.",
        keyboard=cancel(),
    )


@labeler.message(state=TransferState.RECIPIENT)
async def pick_recipient(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            recipient = await character_service.find_character(session, message.text)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return
        recipient_id, recipient_name = recipient.id, recipient.name

    await state_dispenser.set(
        message.peer_id,
        TransferState.AMOUNT,
        sender_id=message.state_peer.payload["sender_id"],
        sender_name=message.state_peer.payload["sender_name"],
        recipient_id=recipient_id,
        recipient_name=recipient_name,
    )
    await message.answer(
        f"Получатель: {recipient_name}.\nСколько Шакеев и за что? Например: «50 за услугу».",
        keyboard=cancel(),
    )


@labeler.message(state=TransferState.AMOUNT)
async def do_transfer(message: Message, is_admin: bool = False, **_: object) -> None:
    payload = message.state_peer.payload
    amount_text, _, reason = message.text.strip().partition(" ")

    async with get_session() as session:
        try:
            amount = parse_positive_int(amount_text, field="Сумма")
            sender = await character_service.require_owned(
                session,
                character_id=payload["sender_id"],
                vk_id=message.from_id,
            )
            await shakei_service.transfer(
                session,
                from_character_id=sender.id,
                to_character_id=payload["recipient_id"],
                amount=amount,
                reason=reason.strip(),
            )
            balance = sender.shakei_balance
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(
        f"Перевёл {amount} Шакеев персонажу {payload['recipient_name']}.\n"
        f"Ваш баланс: {balance}.",
        keyboard=main_menu(is_admin),
    )
