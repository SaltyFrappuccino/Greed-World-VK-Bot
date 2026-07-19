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
        "Формат: ?выдать <ID анкеты> <ID карты> [количество]\n"
        "Пример: ?выдать 12 7 3",
        keyboard=back_to_admin_cards(),
    )


@labeler.message(text=[
    "?выдать <character_id> <card_id>",
    "?выдать <character_id> <card_id> <quantity>",
])
async def grant_card(
    message: Message,
    character_id: str,
    card_id: str,
    quantity: str = "1",
    **_: object,
) -> None:
    try:
        parsed_character_id = parse_positive_int(
            character_id, field="ID анкеты"
        )
        public_card_id = parse_int(card_id.removeprefix("#"), field="Публичный ID карты")
        if public_card_id < 0:
            raise ValidationError("Публичный ID карты не может быть отрицательным.")
        parsed_quantity = parse_positive_int(quantity, field="Количество карт")
        async with get_session() as session:
            card = await card_service.find_card(session, str(public_card_id))
            character = await _get_character(session, parsed_character_id)
            await card_service.grant_card_copies(
                session,
                card.id,
                parsed_character_id,
                quantity=parsed_quantity,
            )
            live_copies = await cards_crud.count_owners(session, card.id)
            limit_text = formatters.format_limit(card, live_copies)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return

    await clear_state(message.peer_id)
    await message.answer(
        f"Карта {formatters.card_public_id(card)} · «{card.name}» выдана в количестве "
        f"{parsed_quantity} персонажу "
        f"#{character.id} · {character.name}.\nПреобразования: {limit_text}",
        keyboard=back_to_admin_cards(),
    )


@labeler.message(text="?забрать")
async def revoke_card_hint(message: Message, **_: object) -> None:
    await message.answer(
        "Формат: ?забрать <ID анкеты> <ID карты> [количество]\n"
        "Пример: ?забрать 12 7 2",
        keyboard=back_to_admin_cards(),
    )


@labeler.message(text=[
    "?забрать <character_id> <card_id>",
    "?забрать <character_id> <card_id> <quantity>",
])
async def revoke_card(
    message: Message,
    character_id: str,
    card_id: str,
    quantity: str = "1",
    **_: object,
) -> None:
    try:
        parsed_character_id = parse_positive_int(
            character_id, field="ID анкеты"
        )
        public_card_id = parse_int(card_id.removeprefix("#"), field="Публичный ID карты")
        if public_card_id < 0:
            raise ValidationError("Публичный ID карты не может быть отрицательным.")
        parsed_quantity = parse_positive_int(quantity, field="Количество карт")
        async with get_session() as session:
            card = await card_service.find_card(session, str(public_card_id))
            character = await _get_character(session, parsed_character_id)
            await card_service.revoke_card_copies(
                session,
                card.id,
                parsed_character_id,
                quantity=parsed_quantity,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return

    await clear_state(message.peer_id)
    await message.answer(
        f"Карта {formatters.card_public_id(card)} · «{card.name}» забрана в количестве "
        f"{parsed_quantity} у персонажа "
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


async def _get_character(session, character_id: int):
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise ValidationError(f"Анкета с ID #{character_id} не найдена.")
    return character
