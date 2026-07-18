import logging

from vkbottle import DocMessagesUploader
from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.admin_menu import (
    admin_cards_menu,
    admin_character_add_menu,
    admin_characters_menu,
    admin_menu,
    back_to_admin,
)
from bot.middlewares.auth import AdminRule
from bot.services import backup_service, character_service, spreadsheet_service
from bot.services.errors import ServiceError
from bot.states import clear_state
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True
logger = logging.getLogger(__name__)


@labeler.message(payload={"cmd": "admin"})
async def show_admin_menu(message: Message, **_: object) -> None:
    await clear_state(message.peer_id)
    await message.answer("Админ-панель:", keyboard=admin_menu())


@labeler.message(payload={"cmd": "admin_characters"})
async def show_characters_menu(message: Message, **_: object) -> None:
    await clear_state(message.peer_id)
    await message.answer("Анкеты:", keyboard=admin_characters_menu())


@labeler.message(payload={"cmd": "admin_character_add_menu"})
async def show_character_add_menu(message: Message, **_: object) -> None:
    await clear_state(message.peer_id)
    await message.answer(
        "Как добавить анкету?", keyboard=admin_character_add_menu()
    )


@labeler.message(payload={"cmd": "admin_cards"})
async def show_cards_menu(message: Message, **_: object) -> None:
    await clear_state(message.peer_id)
    await message.answer("Карты:", keyboard=admin_cards_menu())


@labeler.message(payload={"cmd": "admin_database_backup"})
async def create_database_backup(message: Message, **_: object) -> None:
    await message.answer("Создаю и проверяю бэкап БД…")
    try:
        backup = await backup_service.create_database_backup()
        uploader = DocMessagesUploader(
            message.ctx_api, attachment_name=backup.filename
        )
        attachment = await uploader.upload(
            backup.data,
            peer_id=message.peer_id,
            title=backup.filename,
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin())
        return
    except Exception:
        logger.exception("Не удалось загрузить бэкап БД в VK")
        await message.answer(
            "Бэкап создан, но VK не принял файл. Проверьте права сообщества на документы.",
            keyboard=back_to_admin(),
        )
        return

    size_mb = len(backup.data) / (1024 * 1024)
    await message.answer(
        f"Бэкап готов: {backup.filename} ({size_mb:.2f} МБ).",
        attachment=attachment,
        keyboard=back_to_admin(),
    )


@labeler.message(payload={"cmd": "admin_cards_export"})
async def export_cards_registry(message: Message, **_: object) -> None:
    await message.answer("Собираю реестр карт в XLSX…")
    try:
        async with get_session() as session:
            export = await spreadsheet_service.export_registry(session)
        uploader = DocMessagesUploader(
            message.ctx_api, attachment_name=export.filename
        )
        attachment = await uploader.upload(
            export.data,
            peer_id=message.peer_id,
            title=export.filename,
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin())
        return
    except Exception:
        logger.exception("Не удалось экспортировать реестр карт")
        await message.answer(
            "Не удалось создать или отправить XLSX. Проверьте права сообщества на документы.",
            keyboard=back_to_admin(),
        )
        return
    await message.answer(
        "Экспорт реестра карт готов.",
        attachment=attachment,
        keyboard=admin_cards_menu(),
    )


@labeler.message(payload={"cmd": "admin_pending"})
async def pending_profiles(message: Message, **_: object) -> None:
    async with get_session() as session:
        pending = await character_service.list_pending(session)

    if not pending:
        await message.answer("Анкет на подтверждение нет.", keyboard=back_to_admin())
        return

    lines = [
        f"{character.id}. {character.name} (https://vk.ru/id{character.vk_id})"
        for character in pending
    ]
    await message.answer(
        "Ждут подтверждения:\n\n"
        + "\n".join(lines)
        + "\n\nПодтвердить: ?подтвердить <id>",
        keyboard=back_to_admin(),
    )


@labeler.message(text="?подтвердить <character_id>")
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
