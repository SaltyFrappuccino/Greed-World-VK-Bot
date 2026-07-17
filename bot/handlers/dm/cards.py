from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.engine import get_session
from bot.keyboards.main_menu import back_to_menu, cancel
from bot.services import card_service
from bot.services.errors import ServiceError
from bot.states import CardsState, clear_state, state_dispenser
from bot.utils import formatters

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True


@labeler.message(payload={"cmd": "cards"})
async def ask_query(message: Message, **_: object) -> None:
    async with get_session() as session:
        total = await cards_crud.count_cards(session)

    await state_dispenser.set(message.peer_id, CardsState.SEARCH)
    await message.answer(
        f"В реестре карт: {total}.\nПришлите название или номер Особого слота.",
        keyboard=cancel(),
    )


@labeler.message(state=CardsState.SEARCH)
async def search(message: Message, **_: object) -> None:
    query = message.text.strip()

    async with get_session() as session:
        matches = await cards_crud.search_by_name(session, query, limit=10)

        # Одно совпадение - сразу полная карточка, иначе список для уточнения.
        if len(matches) == 1 or query.isdigit():
            try:
                card = await card_service.find_card(session, query)
            except ServiceError as error:
                await message.answer(str(error), keyboard=cancel())
                return

            live_copies = await cards_crud.count_owners(session, card.id)
            await clear_state(message.peer_id)
            await message.answer(
                formatters.card_full(card, live_copies), keyboard=back_to_menu()
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
