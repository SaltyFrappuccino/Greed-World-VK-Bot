from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.main.trophies import character_trophies_menu
from bot.keyboards.main_menu import cancel
from bot.middlewares.auth import AdminRule
from bot.services import trophy_service
from bot.services.errors import ServiceError
from bot.states import AdminTrophyState, clear_state, state_dispenser
from bot.utils.formatters import format_trophies
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True

HINT = (
    "Пришлите трофей одной строкой:\n"
    "Ранг | Название | Описание | Награда\n\n"
    "Ранги: Бронзовый, Серебряный, Золотой. "
    "Для пустого описания или награды поставьте «-»."
)


@labeler.message(payload_contains={"cmd": "admin_trophy_award"})
async def start_award(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
    except ServiceError as error:
        await message.answer(str(error))
        return
    await state_dispenser.set(
        message.peer_id, AdminTrophyState.AWARD, character_id=character_id
    )
    await message.answer(HINT, keyboard=cancel())


@labeler.message(state=AdminTrophyState.AWARD)
async def save_award(message: Message, **_: object) -> None:
    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 4:
        await message.answer(HINT, keyboard=cancel())
        return
    rank, name, description, reward = parts
    character_id = int(message.state_peer.payload["character_id"])
    try:
        async with get_session() as session:
            trophy = await trophy_service.award(
                session,
                character_id=character_id,
                name=name,
                rank=rank,
                description="" if description == "-" else description,
                reward="" if reward == "-" else reward,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        "Трофей выдан.\n\n" + format_trophies([trophy]),
        keyboard=character_trophies_menu(character_id, is_admin=True),
    )
