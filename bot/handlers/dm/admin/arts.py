from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import character_arts as arts_crud
from bot.database.engine import get_session
from bot.keyboards.main_menu import (
    cancel,
    character_art_delete_confirm_menu,
    character_art_detail_menu,
    character_arts_menu,
)
from bot.middlewares.auth import AdminRule
from bot.services import character_art_service
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminArtState, clear_state, state_dispenser
from bot.utils.photos import largest_photo_url, vk_photo_attachment
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(payload_contains={"cmd": "admin_character_art_add"})
async def start_art_upload(message: Message, **_: object) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
    except ServiceError as error:
        await message.answer(str(error))
        return
    await state_dispenser.set(
        message.peer_id, AdminArtState.UPLOAD, character_id=character_id
    )
    await message.answer(
        "Пришлите от 1 до 10 изображений одним сообщением. Текст сообщения станет "
        "подписью. Если у анкеты ещё нет артов, первый автоматически станет основным.",
        keyboard=cancel(),
    )


@labeler.message(state=AdminArtState.UPLOAD)
async def save_uploaded_arts(message: Message, **_: object) -> None:
    photos = list(message.get_photo_attachments() or [])
    if not 1 <= len(photos) <= 10:
        await message.answer(
            "Нужно прислать от 1 до 10 изображений как фотографии VK.",
            keyboard=cancel(),
        )
        return
    character_id = int(message.state_peer.payload["character_id"])
    try:
        async with get_session() as session:
            created = []
            for photo in photos:
                created.append(
                    await character_art_service.add_from_vk(
                        session,
                        character_id=character_id,
                        source_url=largest_photo_url(photo),
                        vk_attachment=vk_photo_attachment(photo),
                        caption=message.text,
                        admin_vk_id=message.from_id,
                    )
                )
            arts = await arts_crud.list_for_character(session, character_id)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Добавлено артов: {len(created)}. ID: "
        + ", ".join(f"#{art.id}" for art in created),
        keyboard=character_arts_menu(character_id, arts, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_character_art_primary"})
async def set_primary_art(message: Message, **_: object) -> None:
    try:
        art_id = _payload_id(message, "ID арта")
        async with get_session() as session:
            art = await character_art_service.set_primary(
                session, art_id=art_id, admin_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error))
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Арт #{art.id} назначен основным.",
        keyboard=character_art_detail_menu(art, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_character_art_caption"})
async def start_caption_edit(message: Message, **_: object) -> None:
    try:
        art_id = _payload_id(message, "ID арта")
        async with get_session() as session:
            art = await arts_crud.get_by_id(session, art_id)
            if art is None:
                raise ValidationError("Арт не найден.")
    except ServiceError as error:
        await message.answer(str(error))
        return
    await state_dispenser.set(
        message.peer_id,
        AdminArtState.CAPTION,
        art_id=art.id,
        character_id=art.character_id,
    )
    await message.answer(
        f"Текущая подпись: {art.caption or '—'}\n\n"
        "Пришлите новую подпись до 500 символов. Для очистки пришлите «-».",
        keyboard=cancel(),
    )


@labeler.message(state=AdminArtState.CAPTION)
async def save_caption(message: Message, **_: object) -> None:
    art_id = int(message.state_peer.payload["art_id"])
    caption = "" if message.text.strip() == "-" else message.text
    try:
        async with get_session() as session:
            art = await character_art_service.update_caption(
                session,
                art_id=art_id,
                caption=caption,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Подпись арта #{art.id} обновлена.",
        keyboard=character_art_detail_menu(art, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_character_art_delete"})
async def confirm_art_delete(message: Message, **_: object) -> None:
    try:
        art_id = _payload_id(message, "ID арта")
        async with get_session() as session:
            art = await arts_crud.get_by_id(session, art_id)
            if art is None:
                raise ValidationError("Арт не найден.")
    except ServiceError as error:
        await message.answer(str(error))
        return
    await message.answer(
        f"Удалить арт #{art.id} без возможности восстановления?",
        keyboard=character_art_delete_confirm_menu(art),
    )


@labeler.message(payload_contains={"cmd": "admin_character_art_delete_confirm"})
async def delete_art(message: Message, **_: object) -> None:
    try:
        art_id = _payload_id(message, "ID арта")
        async with get_session() as session:
            character_id, _ = await character_art_service.delete_art(
                session, art_id=art_id, admin_vk_id=message.from_id
            )
            arts = await arts_crud.list_for_character(session, character_id)
    except ServiceError as error:
        await message.answer(str(error))
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Арт #{art_id} удалён.",
        keyboard=character_arts_menu(character_id, arts, is_admin=True),
    )


def _payload_id(message: Message, field: str) -> int:
    payload = message.get_payload_json() or {}
    return parse_positive_int(str(payload.get("id", "")), field=field)
