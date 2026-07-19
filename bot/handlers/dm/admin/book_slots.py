from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.main_menu import cancel, profile_menu
from bot.middlewares.auth import AdminRule
from bot.services import book_slot_service
from bot.services.errors import ServiceError
from bot.states import AdminBookState, clear_state, state_dispenser
from bot.utils.validators import parse_int, parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(payload_contains={"cmd": "admin_character_free_slots_up"})
async def upgrade_limit(message: Message, **_: object) -> None:
    try:
        character_id = _character_id(message)
        async with get_session() as session:
            character = await book_slot_service.upgrade_free_slot_limit(
                session, character_id=character_id, admin_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error))
        return
    await message.answer(
        f"Свободных слотов теперь: {character.free_slot_limit}.",
        keyboard=profile_menu(character.id, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_character_free_slots_set"})
async def start_set_limit(message: Message, **_: object) -> None:
    try:
        character_id = _character_id(message)
    except ServiceError as error:
        await message.answer(str(error))
        return
    await state_dispenser.set(
        message.peer_id,
        AdminBookState.FREE_SLOT_LIMIT,
        character_id=character_id,
    )
    await message.answer(
        "Введите новое количество Свободных слотов (не меньше 10 и не меньше занятых).",
        keyboard=cancel(),
    )


@labeler.message(state=AdminBookState.FREE_SLOT_LIMIT)
async def save_limit(message: Message, **_: object) -> None:
    character_id = int(message.state_peer.payload["character_id"])
    try:
        value = parse_int(message.text, field="Количество Свободных слотов")
        async with get_session() as session:
            character = await book_slot_service.set_free_slot_limit(
                session,
                character_id=character_id,
                value=value,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Лимит Свободных слотов установлен: {character.free_slot_limit}.",
        keyboard=profile_menu(character.id, is_admin=True),
    )


def _character_id(message: Message) -> int:
    payload = message.get_payload_json() or {}
    return parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
