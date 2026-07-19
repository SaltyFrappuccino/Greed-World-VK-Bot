from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.main_menu import (
    back_to_menu,
    character_contours_menu,
    contour_detail_menu,
)
from bot.services import contour_service
from bot.services.errors import ServiceError
from bot.states import clear_state
from bot.utils import formatters
from bot.utils.messages import answer_long
from bot.utils.pagination import normalize_page
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True

CONTOUR_PAGE_SIZE = 6


@labeler.message(payload_contains={"cmd": "character_contours"})
async def show_character_contours(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(
            str(payload.get("id", "")), field="ID анкеты"
        )
        await _show_contours_page(
            message, character_id, 0, is_admin=is_admin
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_menu())


@labeler.message(payload_contains={"cmd": "character_contours_page"})
async def show_character_contours_page(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = parse_positive_int(
            str(payload.get("id", "")), field="ID анкеты"
        )
        page = max(int(payload.get("page", 0)), 0)
        await _show_contours_page(
            message, character_id, page, is_admin=is_admin
        )
    except (ServiceError, TypeError, ValueError) as error:
        await message.answer(str(error), keyboard=back_to_menu())


@labeler.message(payload_contains={"cmd": "character_contour_view"})
async def show_contour(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        contour_id = parse_positive_int(
            str(payload.get("id", "")), field="ID Контура"
        )
        async with get_session() as session:
            contour = await contour_service.require_visible_contour(
                session,
                contour_id=contour_id,
                viewer_vk_id=message.from_id,
            )
            text = formatters.format_contour(contour)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_menu())
        return

    await clear_state(message.peer_id)
    await answer_long(
        message, text, keyboard=contour_detail_menu(contour, is_admin=is_admin)
    )


async def _show_contours_page(
    message: Message,
    character_id: int,
    requested_page: int,
    *,
    is_admin: bool,
) -> None:
    async with get_session() as session:
        character = await contour_service.require_visible_character(
            session,
            character_id=character_id,
            viewer_vk_id=message.from_id,
        )
        contours = await contour_service.list_for_character(session, character.id)
        by_slot = {contour.slot: contour for contour in contours}
        page, pages = normalize_page(
            requested_page, character.contour_limit, page_size=CONTOUR_PAGE_SIZE
        )
        first_slot = page * CONTOUR_PAGE_SIZE + 1
        last_slot = min(first_slot + CONTOUR_PAGE_SIZE, character.contour_limit + 1)
        slots = [(slot, by_slot.get(slot)) for slot in range(first_slot, last_slot)]
        text_lines = [
            f"Контуры персонажа #{character.id} · {character.name}",
            f"Занято: {len(contours)}/{character.contour_limit}",
            f"Страница: {page + 1}/{pages}",
            "",
        ]
        for slot, contour in slots:
            if contour is None:
                text_lines.append(f"{slot}. Пустой слот")
            else:
                suffix = " · требуется привязка карт" if not contour.components else ""
                text_lines.append(
                    f"{slot}. #{contour.id} · {contour.name} · "
                    f"карт {len(contour.components)}/{contour.card_capacity}{suffix}"
                )

    await clear_state(message.peer_id)
    await message.answer(
        "\n".join(text_lines),
        keyboard=character_contours_menu(
            character_id, slots, page, pages, is_admin=is_admin
        ),
    )
