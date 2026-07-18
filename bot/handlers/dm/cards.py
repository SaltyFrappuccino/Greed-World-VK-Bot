from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.engine import get_session
from bot.database.models import CardType
from bot.keyboards.main_menu import (
    back_to_menu,
    cancel,
    card_registry_detail_menu,
    card_registry_categories,
    card_registry_menu,
)
from bot.services import card_service
from bot.services.errors import ServiceError
from bot.states import CardsState, clear_state, state_dispenser
from bot.utils import formatters
from bot.utils.pagination import PAGE_SIZE, normalize_page

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True


@labeler.message(payload={"cmd": "cards"})
async def show_registry(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    await clear_state(message.peer_id)
    await message.answer(
        "Выберите раздел реестра карт:",
        keyboard=card_registry_categories(is_admin=is_admin),
    )


@labeler.message(payload_contains={"cmd": "cards_page"})
async def show_registry_page(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    card_type = _type_from_payload(payload)
    if card_type is CardType.GM and not is_admin:
        await message.answer(
            "Карты ГеймМастеров доступны только администраторам.",
            keyboard=back_to_menu(),
        )
        return
    await _show_registry_page(
        message,
        _page_from_payload(payload),
        card_type=card_type,
        is_admin=is_admin,
    )


@labeler.message(payload_contains={"cmd": "card_registry_view"})
async def show_registry_card(
    message: Message, is_admin: bool = False, **_: object
) -> None:
    payload = message.get_payload_json() or {}
    try:
        card_id = int(payload.get("id", 0))
    except (TypeError, ValueError):
        card_id = 0
    page = _page_from_payload(payload)

    async with get_session() as session:
        card = await cards_crud.get_by_id(session, card_id)
        if card is None or (card.card_type is CardType.GM and not is_admin):
            await message.answer("Карта больше не существует.", keyboard=back_to_menu())
            return
        live_copies = await cards_crud.count_owners(session, card.id)

    await clear_state(message.peer_id)
    await message.answer(
        formatters.card_full(card, live_copies),
        keyboard=card_registry_detail_menu(
            card.id, page, card_type=card.card_type, is_admin=is_admin
        ),
    )


@labeler.message(payload={"cmd": "card_search"})
async def ask_query(message: Message, **_: object) -> None:
    async with get_session() as session:
        total = await cards_crud.count_cards(session)

    await state_dispenser.set(message.peer_id, CardsState.SEARCH)
    await message.answer(
        f"В реестре карт: {total}.\n"
        "Пришлите название карты. Можно ввести игровой номер, если он не "
        "повторяется в двух пулах.",
        keyboard=cancel(),
    )


@labeler.message(state=CardsState.SEARCH)
async def search(message: Message, is_admin: bool = False, **_: object) -> None:
    query = message.text.strip()

    async with get_session() as session:
        matches = await cards_crud.search_by_name(session, query, limit=10)
        if not is_admin:
            matches = [card for card in matches if card.card_type is not CardType.GM]

        # Одно совпадение - сразу полная карточка, иначе список для уточнения.
        if len(matches) == 1 or query.isdigit():
            try:
                card = await card_service.find_card(session, query)
                if card.card_type is CardType.GM and not is_admin:
                    raise ServiceError("Карта не найдена.")
            except ServiceError as error:
                await message.answer(str(error), keyboard=cancel())
                return

            live_copies = await cards_crud.count_owners(session, card.id)
            await clear_state(message.peer_id)
            await message.answer(
                formatters.card_full(card, live_copies),
                keyboard=card_registry_detail_menu(
                    card.id, 0, card_type=card.card_type, is_admin=is_admin
                ),
            )
            return

        if not matches:
            await message.answer(
                f"Карта «{query}» не найдена. Попробуйте другое название.", keyboard=cancel()
            )
            return

        await message.answer(
            "Подходит несколько карт - уточните название:\n\n" + formatters.card_list(matches),
            keyboard=cancel(),
        )


async def _show_registry_page(
    message: Message,
    requested_page: int,
    *,
    card_type: CardType,
    is_admin: bool,
) -> None:
    async with get_session() as session:
        total = await cards_crud.count_cards(session, (card_type,))
        page, pages = normalize_page(requested_page, total)
        cards = await cards_crud.list_cards(
            session,
            offset=page * PAGE_SIZE,
            limit=PAGE_SIZE,
            card_types=(card_type,),
        )

    await clear_state(message.peer_id)
    if cards:
        lines = [
            (f"ID БД #{card.id} · " if is_admin else "")
            + formatters.card_list([card])
            for card in cards
        ]
        text = (
            f"{card_type.value} · страница {page + 1}/{pages} · всего {total}\n\n"
            + "\n".join(lines)
            + "\n\nНажмите название карты, чтобы открыть её."
        )
    else:
        text = f"Раздел «{card_type.value}» пока пуст."
    await message.answer(
        text,
        keyboard=card_registry_menu(
            cards, page, pages, card_type=card_type, is_admin=is_admin
        ),
    )


def _page_from_payload(payload: dict[str, object]) -> int:
    try:
        return int(payload.get("page", 0))
    except (TypeError, ValueError):
        return 0


def _type_from_payload(payload: dict[str, object]) -> CardType:
    try:
        card_type = CardType[str(payload.get("type", ""))]
    except KeyError:
        card_type = CardType.SPECIAL
    if card_type not in (
        CardType.SPECIAL,
        CardType.SPELL,
        CardType.CONTOUR,
        CardType.GM,
    ):
        return CardType.SPECIAL
    return card_type
