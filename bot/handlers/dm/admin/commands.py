from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.engine import get_session
from bot.keyboards.admin_menu import back_to_admin_cards, back_to_admin_characters
from bot.middlewares.auth import AdminRule
from bot.services import card_service, shakei_service
from bot.services.errors import ServiceError, ValidationError
from bot.states import clear_state
from bot.utils import formatters
from bot.utils.validators import parse_int, parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(text="?выдать")
async def grant_card_hint(message: Message, **_: object) -> None:
    await message.answer(
        "Формат: ?выдать <ID анкеты> <ID карты>\nПример: ?выдать 12 7",
        keyboard=back_to_admin_cards(),
    )


@labeler.message(text="?выдать <character_id> <card_id>")
async def grant_card(
    message: Message, character_id: str, card_id: str, **_: object
) -> None:
    try:
        parsed_character_id = parse_positive_int(
            character_id, field="ID анкеты"
        )
        parsed_card_id = parse_positive_int(card_id, field="ID карты")
        async with get_session() as session:
            card, character = await _get_card_and_character(
                session, parsed_card_id, parsed_character_id
            )
            await card_service.grant_card(
                session, parsed_card_id, parsed_character_id
            )
            live_copies = await cards_crud.count_owners(session, parsed_card_id)
            limit_text = formatters.format_limit(card, live_copies)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return

    await clear_state(message.peer_id)
    await message.answer(
        f"Карта #{card.id} · «{card.name}» выдана персонажу "
        f"#{character.id} · {character.name}.\nПреобразования: {limit_text}",
        keyboard=back_to_admin_cards(),
    )


@labeler.message(text="?забрать")
async def revoke_card_hint(message: Message, **_: object) -> None:
    await message.answer(
        "Формат: ?забрать <ID анкеты> <ID карты>\nПример: ?забрать 12 7",
        keyboard=back_to_admin_cards(),
    )


@labeler.message(text="?забрать <character_id> <card_id>")
async def revoke_card(
    message: Message, character_id: str, card_id: str, **_: object
) -> None:
    try:
        parsed_character_id = parse_positive_int(
            character_id, field="ID анкеты"
        )
        parsed_card_id = parse_positive_int(card_id, field="ID карты")
        async with get_session() as session:
            card, character = await _get_card_and_character(
                session, parsed_card_id, parsed_character_id
            )
            await card_service.revoke_card(
                session, parsed_card_id, parsed_character_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return

    await clear_state(message.peer_id)
    await message.answer(
        f"Карта #{card.id} · «{card.name}» забрана у персонажа "
        f"#{character.id} · {character.name}.",
        keyboard=back_to_admin_cards(),
    )


@labeler.message(text="?шакеи")
async def shakei_hint(message: Message, **_: object) -> None:
    await message.answer(
        "Формат: ?шакеи <ID анкеты> <изменение>\n"
        "Примеры: ?шакеи 12 +100 или ?шакеи 12 -100",
        keyboard=back_to_admin_characters(),
    )


@labeler.message(text="?шакеи <character_id> <delta>")
async def change_shakei(
    message: Message, character_id: str, delta: str, **_: object
) -> None:
    try:
        parsed_character_id = parse_positive_int(
            character_id, field="ID анкеты"
        )
        parsed_delta = parse_int(delta, field="Изменение Шакеев")
        if parsed_delta == 0:
            raise ValidationError("Изменение Шакеев не может быть нулевым.")

        async with get_session() as session:
            character = await characters_crud.get_by_id(
                session, parsed_character_id
            )
            if character is None:
                raise ValidationError(
                    f"Анкета с ID #{parsed_character_id} не найдена."
                )
            if parsed_delta > 0:
                await shakei_service.grant(
                    session,
                    character_id=parsed_character_id,
                    amount=parsed_delta,
                    admin_vk_id=message.from_id,
                    reason="",
                )
            else:
                await shakei_service.deduct(
                    session,
                    character_id=parsed_character_id,
                    amount=abs(parsed_delta),
                    admin_vk_id=message.from_id,
                    reason="",
                )
            balance = character.shakei_balance
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return

    await clear_state(message.peer_id)
    await message.answer(
        f"Шакеи персонажа #{character.id} · {character.name}: "
        f"{parsed_delta:+d}. Новый баланс: {balance}.",
        keyboard=back_to_admin_characters(),
    )


async def _get_card_and_character(session, card_id: int, character_id: int):
    card = await cards_crud.get_by_id(session, card_id)
    if card is None:
        raise ValidationError(f"Карта с ID #{card_id} не найдена.")
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise ValidationError(f"Анкета с ID #{character_id} не найдена.")
    return card, character
