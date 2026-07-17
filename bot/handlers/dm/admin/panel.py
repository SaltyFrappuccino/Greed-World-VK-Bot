from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.admin_menu import admin_menu, back_to_admin
from bot.middlewares.auth import AdminRule
from bot.services import character_service
from bot.services.errors import ServiceError
from bot.states import clear_state
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(payload={"cmd": "admin"})
async def show_admin_menu(message: Message, **_: object) -> None:
    await clear_state(message.peer_id)
    await message.answer("Админ-панель:", keyboard=admin_menu())


@labeler.message(payload={"cmd": "admin_pending"})
async def pending_profiles(message: Message, **_: object) -> None:
    async with get_session() as session:
        pending = await character_service.list_pending(session)

    if not pending:
        await message.answer("Анкет на подтверждение нет.", keyboard=back_to_admin())
        return

    lines = [f"{character.id}. {character.name} (vk {character.vk_id})" for character in pending]
    await message.answer(
        "Ждут подтверждения:\n\n"
        + "\n".join(lines)
        + "\n\nПодтвердить: ?!подтвердить <id>",
        keyboard=back_to_admin(),
    )


@labeler.message(text="?!подтвердить <character_id>")
async def approve_profile(message: Message, character_id: str, **_: object) -> None:
    async with get_session() as session:
        try:
            parsed_id = parse_positive_int(character_id, field="ID анкеты")
            character = await character_service.approve(session, parsed_id)
            name = character.name
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_admin())
            return

    await message.answer(f"Анкета «{name}» подтверждена.", keyboard=back_to_admin())
