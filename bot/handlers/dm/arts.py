from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import character_arts as arts_crud
from bot.database.crud import characters as characters_crud
from bot.database.engine import get_session
from bot.keyboards.main_menu import (
    back_to_menu,
    character_art_detail_menu,
    character_arts_menu,
)
from bot.services import character_art_service
from bot.services.errors import ServiceError
from bot.states import clear_state
from bot.utils.photos import art_attachment
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True


@labeler.message(payload_contains={"cmd": "character_arts"})
async def show_character_arts(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(str(payload.get("id", "")), field="ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_menu())
        return
    await _show_character_arts(message, character_id, is_admin=is_admin)


async def _show_character_arts(
    message: Message, character_id: int, *, is_admin: bool
) -> None:
    try:
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            arts = await character_art_service.list_visible(
                session,
                character_id=character_id,
                viewer_vk_id=message.from_id,
                is_admin=is_admin,
            )
            attachments = [await art_attachment(message, art) for art in arts]
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_menu())
        return
    await clear_state(message.peer_id)
    text = _gallery_text(character.name, arts)
    await message.answer(
        text,
        keyboard=character_arts_menu(character.id, arts, is_admin=is_admin),
    )
    for index in range(0, len(attachments), 10):
        await message.answer(
            "Арты персонажа:", attachment=",".join(attachments[index : index + 10])
        )


@labeler.message(payload_contains={"cmd": "character_art_view"})
async def show_character_art(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        art_id = parse_positive_int(str(payload.get("id", "")), field="ID арта")
        async with get_session() as session:
            art = await arts_crud.get_by_id(session, art_id)
            if art is None:
                raise ServiceError("Арт не найден.")
            await character_art_service.list_visible(
                session,
                character_id=art.character_id,
                viewer_vk_id=message.from_id,
                is_admin=is_admin,
            )
            attachment = await art_attachment(message, art)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_menu())
        return
    await clear_state(message.peer_id)
    await message.answer(
        _art_text(art),
        attachment=attachment,
        keyboard=character_art_detail_menu(art, is_admin=is_admin),
    )


def _gallery_text(name: str, arts: list) -> str:
    if not arts:
        return f"Арты персонажа «{name}» пока не добавлены."
    lines = [f"Арты персонажа «{name}» · всего {len(arts)}", ""]
    for art in arts:
        marker = "★ основной" if art.is_primary else "дополнительный"
        lines.append(f"#{art.id} · {marker} · {art.caption or 'без подписи'}")
    return "\n".join(lines)


def _art_text(art) -> str:
    return (
        f"Арт #{art.id}{' · основной' if art.is_primary else ''}\n"
        f"Подпись: {art.caption or '—'}\n"
        f"Размер: {art.width}×{art.height} · {art.file_size / 1024 / 1024:.2f} МБ\n"
        f"Формат: {art.mime_type}"
    )
