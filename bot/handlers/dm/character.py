from sqlalchemy.ext.asyncio import AsyncSession
from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.crud import contours as contours_crud
from bot.database.engine import get_session
from bot.database.models import Character
from bot.keyboards.main_menu import (
    back_to_menu,
    cancel,
    character_select_menu,
    profile_edit_menu,
    profile_menu,
)
from bot.services import character_service
from bot.services.errors import ServiceError
from bot.states import ProfileState, clear_state, state_dispenser
from bot.utils import formatters
from bot.utils.messages import answer_long
from bot.utils.validators import parse_int, parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True

EDITABLE_FIELDS = {
    "personality": "характер",
    "biography": "биографию",
    "age": "возраст",
}


@labeler.message(payload={"cmd": "profile"})
async def show_profiles(message: Message, **_: object) -> None:
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
            await _show_character(message, session, characters[0])
            return

    await message.answer(
        "Выберите персонажа:",
        keyboard=character_select_menu("profile_select", characters),
    )


@labeler.message(payload_contains={"cmd": "profile_select"})
async def select_profile(message: Message, **_: object) -> None:
    await clear_state(message.peer_id)
    async with get_session() as session:
        try:
            character = await _owned_from_payload(session, message)
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_menu())
            return
        await _show_character(message, session, character)


@labeler.message(payload_contains={"cmd": "my_cards"})
async def my_cards(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            character = await _owned_from_payload(session, message)
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_menu())
            return

        cards = await cards_crud.list_character_cards(session, character.id)
        text = formatters.card_list(cards) if cards else "Карт пока нет."
        await message.answer(
            f"Карты персонажа {character.name}:\n\n{text}",
            keyboard=profile_menu(character.id),
        )


@labeler.message(payload_contains={"cmd": "profile_edit"})
async def edit_menu(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            character = await _owned_from_payload(session, message)
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_menu())
            return
    await message.answer(
        "Что правим? Статы можно расставить до подтверждения анкеты; "
        "рейтинг и Шакеи меняет админ.",
        keyboard=profile_edit_menu(
            character.id, can_edit_stats=not character.is_approved
        ),
    )


@labeler.message(payload_contains={"cmd": "edit_field"})
async def pick_field(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    field = payload.get("field")
    if field not in EDITABLE_FIELDS and field not in character_service.STAT_FIELDS:
        await message.answer("Это поле править нельзя.", keyboard=back_to_menu())
        return

    async with get_session() as session:
        try:
            character = await _owned_from_payload(session, message)
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_menu())
            return

    await state_dispenser.set(
        message.peer_id,
        ProfileState.EDIT_VALUE,
        field=field,
        character_id=character.id,
    )
    hint = EDITABLE_FIELDS.get(field, character_service.STAT_FIELDS.get(field, "значение"))
    await message.answer(f"Пришлите новое значение: {hint}.", keyboard=cancel())


@labeler.message(state=ProfileState.EDIT_VALUE)
async def save_field(message: Message, **_: object) -> None:
    field = message.state_peer.payload["field"]
    character_id = message.state_peer.payload["character_id"]

    async with get_session() as session:
        try:
            character = await character_service.require_owned(
                session, character_id=character_id, vk_id=message.from_id
            )
            if field in character_service.STAT_FIELDS:
                value = parse_int(message.text, field="Значение стата")
                await character_service.set_pending_stat(session, character, field, value)
            else:
                value = (
                    parse_int(message.text, field="Возраст")
                    if field == "age"
                    else message.text.strip()
                )
                await character_service.update_profile(session, character, **{field: value})
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    title = EDITABLE_FIELDS.get(field, character_service.STAT_FIELDS.get(field, field))
    await message.answer(
        f"Готово: {title} обновлён(а).",
        keyboard=profile_menu(character_id),
    )


async def _owned_from_payload(session: AsyncSession, message: Message) -> Character:
    payload = message.get_payload_json() or {}
    character_id = parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
    return await character_service.require_owned(
        session, character_id=character_id, vk_id=message.from_id
    )


async def _show_character(
    message: Message, session: AsyncSession, character: Character
) -> None:
    cards = await cards_crud.list_character_cards(session, character.id)
    contours = await contours_crud.list_for_character(session, character.id)
    await answer_long(
        message,
        formatters.character_profile(character, cards, contours),
        keyboard=profile_menu(character.id),
    )
