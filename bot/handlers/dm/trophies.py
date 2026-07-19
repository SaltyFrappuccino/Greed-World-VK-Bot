from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import characters as characters_crud
from bot.database.crud import trophies as trophies_crud
from bot.database.engine import get_session
from bot.keyboards.main.trophies import character_trophies_menu
from bot.keyboards.main_menu import back_to_menu, cancel
from bot.services.errors import ServiceError
from bot.states import clear_state
from bot.utils.formatters import format_trophies
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True


@labeler.message(payload_contains={"cmd": "character_trophies"})
async def show_trophies(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None or (not character.is_approved and not is_admin):
                await message.answer("Анкета не найдена.", keyboard=back_to_menu())
                return
            trophies = await trophies_crud.list_for_character(session, character.id)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_menu())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"🏆 Трофеи персонажа #{character.id} · {character.name}\n\n"
        + format_trophies(trophies),
        keyboard=character_trophies_menu(character.id, is_admin=is_admin),
    )
