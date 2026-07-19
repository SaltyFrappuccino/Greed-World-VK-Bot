import re

from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import trophies as trophies_crud
from bot.database.engine import get_session
from bot.middlewares.auth import AdminRule
from bot.services import character_service, trophy_service
from bot.services.errors import ServiceError, ValidationError
from bot.utils.formatters import format_trophies
from bot.utils.validators import extract_vk_id

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=True)])
labeler.vbml_ignore_case = True

admin_labeler = BotLabeler(auto_rules=[PeerRule(from_chat=True), AdminRule()])
admin_labeler.vbml_ignore_case = True

AWARD_HINT = (
    "Формат:\n"
    "?выдатьтрофей @игрок | Ранг | Название | Описание | Награда\n"
    "или\n"
    "?выдатьтрофей @игрок | Ранг | Название | Награда\n\n"
    "Ранги: Бронзовый, Серебряный, Золотой. "
    "Если описания или награды нет, поставьте «-»."
)


@labeler.message(text="?трофеи")
async def own_trophies(message: Message, **_: object) -> None:
    await _show_for_vk(message, message.from_id)


@labeler.message(text="?трофеи <query>")
async def mentioned_trophies(message: Message, query: str, **_: object) -> None:
    vk_id = extract_vk_id(query)
    if vk_id is None:
        await message.answer("Упомяните игрока: ?трофеи [id123|Слава]")
        return
    await _show_for_vk(message, vk_id, query=query)


@admin_labeler.message(text="?выдатьтрофей")
async def award_without_arguments(message: Message, **_: object) -> None:
    await message.answer(AWARD_HINT)


@admin_labeler.message(text="?выдатьтрофей <args>")
async def award_trophy(message: Message, args: str, **_: object) -> None:
    # Extract target (mention or id) as the first token. VK mentions are like [id123|Name]
    m = re.match(r"^\s*(\[[^\]]+\]|\S+)\s*\|\s*(.*)$", args, flags=re.DOTALL)
    if not m:
        await message.answer("Неверный формат команды.\n\n" + AWARD_HINT)
        return
    target = m.group(1).strip()
    rest = m.group(2).strip()

    parts = [part.strip() for part in re.split(r"\s*\|\s*", rest)]
    # Accept either 4 parts (rank|name|description|reward) or 3 parts (rank|name|reward)
    if len(parts) == 4:
        rank, name, description, reward = parts
    elif len(parts) == 3:
        rank, name, reward = parts
        description = "-"
    else:
        await message.answer("Неверное число частей команды.\n\n" + AWARD_HINT)
        return

    vk_id = extract_vk_id(target)
    if vk_id is None:
        await message.answer("В первой части команды упомяните игрока или укажите его id.\n\n" + AWARD_HINT)
        return
    try:
        async with get_session() as session:
            character = await _resolve_mentioned_character(session, vk_id, target)
            trophy = await trophy_service.award(
                session,
                character_id=character.id,
                name=name,
                rank=rank,
                description="" if description == "-" else description,
                reward="" if reward == "-" else reward,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error))
        return
    await message.answer(
        f"Трофей выдан персонажу #{character.id} · {character.name}.\n\n"
        + format_trophies([trophy])
    )


async def _show_for_vk(message: Message, vk_id: int, *, query: str = "") -> None:
    try:
        async with get_session() as session:
            character = await _resolve_mentioned_character(session, vk_id, query)
            trophies = await trophies_crud.list_for_character(session, character.id)
    except ServiceError as error:
        await message.answer(str(error))
        return
    await message.answer(
        f"🏆 Трофеи персонажа #{character.id} · {character.name}\n\n"
        + format_trophies(trophies)
    )


async def _resolve_mentioned_character(session, vk_id: int, query: str):
    characters = await character_service.list_by_vk_id(session, vk_id)
    if not characters:
        raise ValidationError("У упомянутого пользователя нет анкет.")
    if len(characters) == 1:
        return characters[0]
    id_match = re.search(r"#(\d+)", query)
    if id_match:
        character_id = int(id_match.group(1))
        for character in characters:
            if character.id == character_id:
                return character
        raise ValidationError("Упомянутому игроку не принадлежит анкета с таким ID.")
    variants = ", ".join(f"#{item.id} · {item.name}" for item in characters)
    raise ValidationError(
        f"У игрока несколько анкет: {variants}. Добавьте нужный #ID рядом с упоминанием."
    )
