import re

from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import trophies as trophies_crud
from bot.database.engine import get_session
from bot.middlewares.auth import AdminRule
from bot.services import character_service, trophy_service
from bot.services.errors import ServiceError, ValidationError
from bot.utils.formatters import format_trophies
from bot.utils.validators import extract_vk_id, parse_positive_int

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
    m = re.match(r"^\s*(\[[^\]]+\]|\S+)\s*\|\s*(.*)$", args, flags=re.DOTALL)
    if not m:
        await message.answer("Неверный формат команды.\n\n" + AWARD_HINT)
        return
    target = m.group(1).strip()
    rest = m.group(2).strip()

    parts = [part.strip() for part in re.split(r"\s*\|\s*", rest)]
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


@admin_labeler.message(text="?удалитьтрофей")
async def delete_without_arguments(message: Message, **_: object) -> None:
    await message.answer(
        "Формат:\n?удалитьтрофей @игрок|id или #ID_анкеты номер_трофея\n"
        "Примеры:\n?удалитьтрофей [id123|Пользователь] 2\n?удалитьтрофей #45 1"
    )


@admin_labeler.message(text="?удалитьтрофей <args>")
async def delete_trophy(message: Message, args: str, **_: object) -> None:
    m = re.match(r"^\s*(\[[^\]]+\]|#?\d+|\S+)\s+(\d+)\s*$", args)
    if not m:
        await message.answer(
            "Неверный формат.\n\nФормат: ?удалитьтрофей @игрок|id или #ID_анкеты номер_трофея"
        )
        return
    target = m.group(1).strip()
    index = int(m.group(2))

    try:
        async with get_session() as session:
            if extract_vk_id(target) is not None:
                vk_id = extract_vk_id(target)
                character = await _resolve_mentioned_character(session, vk_id, target)
            else:
                character = await character_service.find_character(session, target)

            trophies = await trophies_crud.list_for_character(session, character.id)
            if not trophies:
                raise ValidationError("У персонажа нет трофеев.")
            if index <= 0 or index > len(trophies):
                raise ValidationError(
                    f"Неверный номер трофея. У персонажа {len(trophies)} трофеев."
                )
            trophy = trophies[index - 1]

            deleted = await trophy_service.remove(
                session, trophy_id=trophy.id, admin_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error))
        return
    await message.answer(
        f"Трофей удалён #{deleted.id} · {deleted.name} (персонаж #{character.id} · {character.name}).\n\n"
        + format_trophies([deleted])
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
        + (
            "".join(
                f"{i+1}. {('🥉' if t.rank.name=='BRONZE' else '🥈' if t.rank.name=='SILVER' else '🥇')} {t.name} — {t.rank.value}\n"
                for i, t in enumerate(trophies)
            )
        )
        + "\n\n"
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
