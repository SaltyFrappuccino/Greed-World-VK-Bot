from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.crud import character_arts as arts_crud
from bot.database.crud import trophies as trophies_crud
from bot.database.engine import get_session
from bot.services import book_slot_service, card_service, character_service
from bot.services.errors import ServiceError
from bot.utils import formatters
from bot.utils.messages import answer_long
from bot.utils.validators import extract_vk_id, strip_mentions
from bot.utils.photos import art_attachment

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=True)])
labeler.vbml_ignore_case = True

HELP_TEXT = """Команды Жадного Мира:

?карта [название или публичный ID] — карточка из реестра
?профиль — своя анкета
?профиль Имя или ID — чужая анкета (или ответом/упоминанием)
?визитка [Имя или ID] — графическая карточка персонажа
?трофеи [@игрок] — посмотреть трофеи персонажа
?кубик — бросок 1–20
?кубик 6 — бросок 1–6
?кубик 1 20 — бросок в своих границах
?использовать [#ID] Название [xКоличество] @игрок — потратить Заклинание или Обычную карту
?помощь — этот список

Всё остальное - в личных сообщениях сообщества."""


@labeler.message(text=["?помощь", "?помощь <_>"])
async def help_command(message: Message, **_: object) -> None:
    await message.answer(HELP_TEXT)


@labeler.message(text="?карта")
async def card_without_query(message: Message, **_: object) -> None:
    await message.answer("Укажите название: ?карта Ясень")


@labeler.message(text="?карта <query>")
async def card_command(message: Message, query: str, **_: object) -> None:
    async with get_session() as session:
        try:
            card = await card_service.find_card(session, query)
        except ServiceError as error:
            await message.answer(str(error))
            return

        live_copies = await cards_crud.count_owners(session, card.id)
        card.copies_count = live_copies
        await message.answer(formatters.card_short(card))


@labeler.message(text=["?профиль", "?анкета"])
async def own_profile(message: Message, **_: object) -> None:
    async with get_session() as session:
        characters = await character_service.list_by_vk_id(session, message.from_id)
        if not characters:
            await message.answer("У вас нет анкет. Обратитесь к администратору.")
            return
        if len(characters) > 1:
            names = ", ".join(
                f"#{character.id} · {character.name}" for character in characters
            )
            await message.answer(
                f"Ваши персонажи: {names}. Используйте ?профиль ID или ?профиль Имя."
            )
            return

        character = characters[0]
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
            formatters.character_profile(character, cards, trophies=trophies, book_slots=slots),
            attachment=attachment,
        )


@labeler.message(text=["?профиль <query>", "?анкета <query>"])
async def other_profile(message: Message, query: str, **_: object) -> None:
    async with get_session() as session:
        try:
            character = await _resolve_target(session, message, query)
            cards = await cards_crud.list_character_cards(session, character.id)
            trophies = await trophies_crud.list_for_character(session, character.id)
            slots = await book_slot_service.get_usage(session, character.id)
            primary_art = await arts_crud.get_primary(session, character.id)
        except ServiceError as error:
            await message.answer(str(error))
            return

        attachment = (
            await art_attachment(message, primary_art)
            if primary_art is not None
            else None
        )
        await answer_long(
            message,
            formatters.character_profile(character, cards, trophies=trophies, book_slots=slots),
            attachment=attachment,
        )


async def _resolve_target(session, message: Message, query: str):
    """Кого спрашивают: упоминание [id123|...], ответ на сообщение или имя персонажа."""
    mentioned_vk_id = extract_vk_id(query)
    if mentioned_vk_id is not None:
        return await character_service.require_single_by_vk_id(session, mentioned_vk_id)

    reply = message.reply_message
    name = strip_mentions(query)
    if not name and reply is not None:
        return await character_service.require_single_by_vk_id(session, reply.from_id)

    return await character_service.find_character(session, name)
