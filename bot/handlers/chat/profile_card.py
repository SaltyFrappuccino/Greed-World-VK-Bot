import logging

from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.services import character_service, profile_card_service
from bot.services.errors import ServiceError
from bot.services.profile_card_storage_service import read_bytes
from bot.utils.photos import upload_message_photo
from bot.utils.validators import extract_vk_id, strip_mentions

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=True)])
labeler.vbml_ignore_case = True
logger = logging.getLogger(__name__)


@labeler.message(text=["?визитка", "?карточка"])
async def own_profile_card(message: Message, **_: object) -> None:
    async with get_session() as session:
        characters = await character_service.list_by_vk_id(session, message.from_id)
        if not characters:
            await message.answer("У вас нет анкет. Обратитесь к администратору.")
            return
        if len(characters) > 1:
            choices = ", ".join(f"#{item.id} · {item.name}" for item in characters)
            await message.answer(
                f"У вас несколько персонажей: {choices}. Используйте "
                "?визитка ID или ?визитка Имя."
            )
            return
        character_id = characters[0].id
    await _send_profile_card(message, character_id)


@labeler.message(text=["?визитка <query>", "?карточка <query>"])
async def selected_profile_card(
    message: Message, query: str, **_: object
) -> None:
    try:
        async with get_session() as session:
            character = await _resolve_target(session, message, query)
            character_id = character.id
    except ServiceError as error:
        await message.answer(str(error))
        return
    await _send_profile_card(message, character_id)


async def _send_profile_card(message: Message, character_id: int) -> None:
    try:
        async with get_session() as session:
            result = await profile_card_service.get_or_create(session, character_id)
        attachment = result.cache.vk_attachment
        if not attachment:
            data = result.data or read_bytes(result.cache.storage_key)
            attachment = await upload_message_photo(
                message.ctx_api,
                message.peer_id,
                data,
                filename=f"profile_card_{character_id}.png",
                content_type="image/png",
            )
            async with get_session() as session:
                await profile_card_service.remember_vk_attachment(
                    session,
                    character_id=character_id,
                    input_hash=result.cache.input_hash,
                    attachment=attachment,
                )
    except ServiceError as error:
        await message.answer(str(error))
        return
    except Exception:
        logger.exception("Не удалось создать или отправить визитку персонажа")
        await message.answer(
            "Не удалось создать или отправить визитку персонажа. Подробности записаны в лог."
        )
        return
    await message.answer(
        f"Визитка персонажа #{character_id} · {result.character_name}",
        attachment=attachment,
    )


async def _resolve_target(session, message: Message, query: str):
    mentioned_vk_id = extract_vk_id(query)
    if mentioned_vk_id is not None:
        return await character_service.require_single_by_vk_id(
            session, mentioned_vk_id
        )
    name = strip_mentions(query)
    if not name and message.reply_message is not None:
        return await character_service.require_single_by_vk_id(
            session, message.reply_message.from_id
        )
    return await character_service.find_character(session, name)
