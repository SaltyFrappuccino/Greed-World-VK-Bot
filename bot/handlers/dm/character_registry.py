from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import contours as contours_crud
from bot.database.engine import get_session
from bot.keyboards.main_menu import (
    back_to_menu,
    character_registry_detail_menu,
    character_registry_menu,
)
from bot.services import character_service
from bot.states import clear_state
from bot.utils import formatters
from bot.utils.messages import answer_long
from bot.utils.pagination import PAGE_SIZE, normalize_page

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True


@labeler.message(payload={"cmd": "character_registry"})
async def show_registry(message: Message, is_admin: bool = False, **_: object) -> None:
    await _show_registry_page(message, 0, is_admin=is_admin)


@labeler.message(payload_contains={"cmd": "character_registry_page"})
async def show_registry_page(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    await _show_registry_page(
        message, _page_from_payload(payload), is_admin=is_admin
    )


@labeler.message(payload_contains={"cmd": "character_registry_view"})
async def show_character(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = int(payload.get("id", 0))
    except (TypeError, ValueError):
        character_id = 0
    page = _page_from_payload(payload)

    async with get_session() as session:
        character = await characters_crud.get_by_id(session, character_id)
        if character is None or (not character.is_approved and not is_admin):
            await message.answer("Анкета не найдена.", keyboard=back_to_menu())
            return
        cards = await cards_crud.list_character_cards(session, character.id)
        contours = await contours_crud.list_for_character(session, character.id)
        text = (
            f"ID анкеты: #{character.id}\nВладелец: VK {character.vk_id}\n\n"
            + formatters.character_profile(character, cards, contours)
        )

    await clear_state(message.peer_id)
    await answer_long(
        message,
        text,
        keyboard=character_registry_detail_menu(
            character.id,
            page,
            is_admin=is_admin,
        ),
    )


async def _show_registry_page(
    message: Message, requested_page: int, *, is_admin: bool
) -> None:
    async with get_session() as session:
        total = await character_service.count_registry(
            session, include_unapproved=is_admin
        )
        page, pages = normalize_page(requested_page, total)
        characters = await character_service.list_registry(
            session,
            offset=page * PAGE_SIZE,
            limit=PAGE_SIZE,
            include_unapproved=is_admin,
        )

    await clear_state(message.peer_id)
    if characters:
        lines = []
        for character in characters:
            status = " · не подтверждена" if not character.is_approved else ""
            lines.append(
                f"#{character.id} · {character.name} · VK {character.vk_id} · "
                f"{character.overall_rating.value}{status}"
            )
        text = (
            f"Реестр анкет · страница {page + 1}/{pages} · всего {total}\n\n"
            + "\n".join(lines)
            + "\n\nНажмите персонажа, чтобы открыть анкету."
        )
    else:
        text = "Реестр анкет пока пуст."
    await message.answer(
        text, keyboard=character_registry_menu(characters, page, pages)
    )


def _page_from_payload(payload: dict[str, object]) -> int:
    try:
        return int(payload.get("page", 0))
    except (TypeError, ValueError):
        return 0
