from vkbottle.bot import Message

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.engine import get_session
from bot.database.models import CardType
from bot.keyboards.admin_menu import (
    admin_cards_menu,
    admin_character_cards_menu,
    admin_characters_menu,
    admin_menu,
    card_owners_menu,
    selected_shakei_action_menu,
)
from bot.keyboards.main_menu import (
    card_registry_categories,
    card_registry_detail_menu,
    character_registry_detail_menu,
    contour_detail_menu,
    main_menu,
)
from bot.services import contour_service
from bot.utils import formatters


async def render_return(
    message: Message,
    context: dict[str, object],
    *,
    is_admin: bool,
) -> None:
    """Показать родительский экран после отмены текущего ввода."""
    screen = str(context.get("screen", "main"))
    target_id = _id(context.get("id"))

    if screen == "admin" and is_admin:
        await message.answer("Отменено. Возвращаю в админ-панель.", keyboard=admin_menu())
        return
    if screen == "admin_cards" and is_admin:
        await message.answer("Отменено. Возвращаю в раздел «Карты».", keyboard=admin_cards_menu())
        return
    if screen == "admin_characters" and is_admin:
        await message.answer("Отменено. Возвращаю в раздел «Анкеты».", keyboard=admin_characters_menu())
        return
    if screen == "cards":
        await message.answer(
            "Отменено. Выберите раздел реестра карт:",
            keyboard=card_registry_categories(is_admin=is_admin),
        )
        return
    if screen == "cards_page":
        from bot.handlers.dm.cards import _show_registry_page

        try:
            card_type = CardType[str(context.get("type", "SPECIAL"))]
            page = max(int(context.get("page", 0)), 0)
        except (KeyError, TypeError, ValueError):
            card_type, page = CardType.SPECIAL, 0
        await _show_registry_page(
            message,
            page,
            card_type=card_type,
            is_admin=is_admin,
        )
        return
    if screen == "character_cards" and is_admin and target_id:
        await _character_cards(message, target_id)
        return
    if screen == "card_owners" and is_admin and target_id:
        await _card_owners(message, target_id)
        return
    if screen == "character_shakei" and is_admin and target_id:
        await _character_shakei(message, target_id)
        return
    if screen == "card" and target_id:
        await _card(message, target_id, is_admin=is_admin)
        return
    if screen == "character" and target_id:
        await _character(message, target_id, is_admin=is_admin)
        return
    if screen == "character_contours" and target_id:
        from bot.handlers.dm.contours import _show_contours_page

        await _show_contours_page(message, target_id, 0, is_admin=is_admin)
        return
    if screen == "character_arts" and target_id:
        from bot.handlers.dm.arts import _show_character_arts

        await _show_character_arts(message, target_id, is_admin=is_admin)
        return
    if screen == "contour" and target_id:
        await _contour(message, target_id, is_admin=is_admin)
        return

    await message.answer("Отменено. Возвращаю в меню.", keyboard=main_menu(is_admin))


async def _character_cards(message: Message, character_id: int) -> None:
    async with get_session() as session:
        character = await characters_crud.get_by_id(session, character_id)
        if character is None:
            await message.answer("Анкета больше не существует.", keyboard=admin_characters_menu())
            return
        ownerships = await cards_crud.list_character_ownerships(session, character_id)
        holdings = formatters.character_card_holdings(ownerships)
    await message.answer(
        f"Отменено. Карты персонажа #{character.id} · {character.name}\n\n{holdings}",
        keyboard=admin_character_cards_menu(character.id),
    )


async def _card_owners(message: Message, card_id: int) -> None:
    async with get_session() as session:
        card = await cards_crud.get_by_id(session, card_id)
        if card is None:
            await message.answer("Карта больше не существует.", keyboard=admin_cards_menu())
            return
        ownerships = await cards_crud.list_card_ownerships(session, card_id)
        holdings = formatters.card_owner_holdings(ownerships)
    await message.answer(
        f"Отменено. Владельцы карты #{card.id} · {card.name}\n\n{holdings}",
        keyboard=card_owners_menu(card.id),
    )


async def _character_shakei(message: Message, character_id: int) -> None:
    async with get_session() as session:
        character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        await message.answer("Анкета больше не существует.", keyboard=admin_characters_menu())
        return
    await message.answer(
        f"Отменено. Шакеи персонажа #{character.id} · {character.name}\n"
        f"Баланс: {character.shakei_balance}.\n\nВыберите действие:",
        keyboard=selected_shakei_action_menu(character.id),
    )


async def _card(message: Message, card_id: int, *, is_admin: bool) -> None:
    async with get_session() as session:
        card = await cards_crud.get_by_id(session, card_id)
        if card is not None:
            live_copies = await cards_crud.count_owners(session, card.id)
    if card is None:
        await message.answer("Карта больше не существует.", keyboard=card_registry_categories(is_admin=is_admin))
        return
    await message.answer(
        "Отменено.\n\n" + formatters.card_full(card, live_copies),
        keyboard=card_registry_detail_menu(
            card.id, 0, card_type=card.card_type, is_admin=is_admin
        ),
    )


async def _character(message: Message, character_id: int, *, is_admin: bool) -> None:
    async with get_session() as session:
        character = await characters_crud.get_by_id(session, character_id)
        cards = (
            await cards_crud.list_character_cards(session, character_id)
            if character is not None
            else []
        )
    if character is None:
        await message.answer("Анкета больше не существует.", keyboard=main_menu(is_admin))
        return
    await message.answer(
        f"Отменено.\n\nВладелец: https://vk.ru/id{character.vk_id}\n\n"
        + formatters.character_profile(character, cards),
        keyboard=character_registry_detail_menu(
            character.id,
            0,
            is_admin=is_admin,
            can_view_contours=is_admin or character.vk_id == message.from_id,
        ),
    )


async def _contour(message: Message, contour_id: int, *, is_admin: bool) -> None:
    async with get_session() as session:
        contour = await contour_service.require_visible_contour(
            session,
            contour_id=contour_id,
            viewer_vk_id=message.from_id,
        )
    await message.answer(
        "Отменено.\n\n" + formatters.format_contour(contour),
        keyboard=contour_detail_menu(contour, is_admin=is_admin),
    )


def _id(value: object) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
