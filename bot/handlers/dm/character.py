import logging

from sqlalchemy.ext.asyncio import AsyncSession
from vkbottle import DocMessagesUploader
from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.crud import character_arts as arts_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import trophies as trophies_crud
from bot.database.engine import get_session
from bot.database.models import Character
from bot.keyboards.main_menu import (
    back_to_menu,
    character_select_menu,
    profile_menu,
)
from bot.services import book_slot_service, character_service, spreadsheet_service
from bot.services.errors import PermissionDenied, ServiceError
from bot.states import clear_state
from bot.utils import formatters
from bot.utils.messages import answer_long
from bot.utils.validators import parse_positive_int
from bot.utils.photos import art_attachment

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True
logger = logging.getLogger(__name__)

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
        slots = await book_slot_service.get_usage(session, character.id)
        text = formatters.character_card_holdings(ownerships, slots)
        await message.answer(
            f"Карты персонажа {character.name}:\n\n{text}",
            keyboard=profile_menu(character.id, is_admin=is_admin),
        )


@labeler.message(payload_contains={"cmd": "character_cards_export"})
async def export_character_cards(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(
            str(payload.get("id", "")), field="ID анкеты"
        )
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise PermissionDenied("Анкета не найдена.")
            if character.vk_id != message.from_id and not is_admin:
                raise PermissionDenied(
                    "Экспорт доступен только владельцу анкеты и администратору."
                )
            export = await spreadsheet_service.export_character_cards(
                session, character_id
            )
        uploader = DocMessagesUploader(
            message.ctx_api, attachment_name=export.filename
        )
        attachment = await uploader.upload(
            export.data,
            peer_id=message.peer_id,
            title=export.filename,
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_menu())
        return
    except Exception:
        logger.exception("Не удалось экспортировать карты персонажа")
        await message.answer(
            "Не удалось создать или отправить XLSX. Проверьте права сообщества на документы.",
            keyboard=back_to_menu(),
        )
        return
    await message.answer(
        f"Экспорт карт персонажа «{character.name}» готов.",
        attachment=attachment,
        keyboard=profile_menu(character.id, is_admin=is_admin),
    )


@labeler.message(payload_contains={"cmd": "character_profile_export"})
async def export_character_profile(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(
            str(payload.get("id", "")), field="ID анкеты"
        )
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise PermissionDenied("Анкета не найдена.")
            if character.vk_id != message.from_id and not is_admin:
                raise PermissionDenied(
                    "Экспорт доступен только владельцу анкеты и администратору."
                )
            export = await spreadsheet_service.export_character_profile(
                session, character_id
            )
        uploader = DocMessagesUploader(
            message.ctx_api, attachment_name=export.filename
        )
        attachment = await uploader.upload(
            export.data,
            peer_id=message.peer_id,
            title=export.filename,
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_menu())
        return
    except Exception:
        logger.exception("Не удалось экспортировать анкету персонажа")
        await message.answer(
            "Не удалось создать или отправить XLSX. Проверьте права сообщества на документы.",
            keyboard=back_to_menu(),
        )
        return
    await message.answer(
        f"Полный экспорт анкеты «{character.name}» готов.",
        attachment=attachment,
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
    trophies = await trophies_crud.list_for_character(session, character.id)
    slots = await book_slot_service.get_usage(session, character.id)
    primary_art = await arts_crud.get_primary(session, character.id)
    attachment = (
        await art_attachment(message, primary_art)
        if primary_art is not None
        else None
    )
    await answer_long(
        message,
        formatters.character_profile(
            character, cards, trophies=trophies, book_slots=slots
        ),
        keyboard=profile_menu(character.id, is_admin=is_admin),
        attachment=attachment,
    )
