from sqlalchemy.ext.asyncio import AsyncSession
from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.engine import get_session
from bot.database.models import Character
from bot.keyboards.main_menu import (
    back_to_menu,
    character_select_menu,
    profile_menu,
)
from bot.services import character_service
from bot.services.errors import ServiceError
from bot.states import clear_state
from bot.utils import formatters
from bot.utils.messages import answer_long
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True

@labeler.message(payload={"cmd": "profile"})
async def show_profiles(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    await clear_state(message.peer_id)
    async with get_session() as session:
        characters = await character_service.list_by_vk_id(session, message.from_id)
        if not characters:
            await message.answer(
                "У вас пока нет анкет. Их добавляет администратор.",
                keyboard=back_to_menu(),
            )
            return
        if len(characters) == 1:
            await _show_character(
                message, session, characters[0], is_admin=is_admin
            )
            return

    await message.answer(
        "Выберите персонажа:",
        keyboard=character_select_menu("profile_select", characters),
    )


@labeler.message(payload_contains={"cmd": "profile_select"})
async def select_profile(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    await clear_state(message.peer_id)
    async with get_session() as session:
        try:
            character = await _owned_from_payload(session, message)
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_menu())
            return
        await _show_character(message, session, character, is_admin=is_admin)


@labeler.message(payload_contains={"cmd": "my_cards"})
async def my_cards(message: Message, is_admin: bool = False, **_: object) -> None:
    async with get_session() as session:
        try:
            character = await _owned_from_payload(session, message)
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_menu())
            return

        ownerships = await cards_crud.list_character_ownerships(session, character.id)
        text = formatters.character_card_holdings(ownerships)
        await message.answer(
            f"Карты персонажа {character.name}:\n\n{text}",
            keyboard=profile_menu(character.id, is_admin=is_admin),
        )


async def _owned_from_payload(session: AsyncSession, message: Message) -> Character:
    payload = message.get_payload_json() or {}
    character_id = parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
    return await character_service.require_owned(
        session, character_id=character_id, vk_id=message.from_id
    )


async def _show_character(
    message: Message,
    session: AsyncSession,
    character: Character,
    *,
    is_admin: bool,
) -> None:
    cards = await cards_crud.list_character_cards(session, character.id)
    await answer_long(
        message,
        formatters.character_profile(character, cards),
        keyboard=profile_menu(character.id, is_admin=is_admin),
    )
