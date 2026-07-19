from vkbottle.bot import Message

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.engine import get_session
from bot.database.models import CardType
from bot.keyboards.admin_menu import (
    back_to_admin_cards,
    admin_character_cards_menu,
    ai_collect_menu,
    ai_confirm_menu,
    card_add_mode_menu,
    card_rarity_menu,
    card_type_menu,
    confirm_menu,
    contour_subtype_menu,
    skip_card_field_menu,
    special_card_limit_menu,
)
from bot.keyboards.main_menu import cancel, card_registry_detail_menu
from bot.middlewares.auth import AdminRule
from bot.services import ai_service, card_service
from bot.services.card_template_service import (
    CONTOUR_SUBTYPES,
    parse_card_template,
    parse_card_type,
    template_for,
)
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminCardState, clear_state, state_dispenser
from bot.utils import formatters
from bot.utils.messages import answer_long
from bot.utils.validators import (
    parse_optional_limit,
    parse_optional_slot_number,
    parse_positive_int,
    parse_rarity,
)
from bot.handlers.dm.admin.card_handlers.routing import labeler
from bot.handlers.dm.admin.card_handlers.wizard import _create_wizard_card, _wizard_payload


@labeler.message(payload={"cmd": "admin_card_add"})
async def start_add(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCardState.TYPE)
    await message.answer("Сначала выберите тип карты:", keyboard=card_type_menu())


@labeler.message(payload_contains={"cmd": "admin_card_type"})
async def choose_card_type(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    try:
        card_type = parse_card_type(str(payload.get("type", "")))
    except ServiceError as error:
        await message.answer(str(error), keyboard=card_type_menu())
        return

    if card_type is CardType.ORDINARY:
        await state_dispenser.set(
            message.peer_id,
            AdminCardState.ORDINARY_CHARACTER,
            card_type=card_type.name,
        )
        await message.answer(
            "Обычная карта создаётся сразу у персонажа и не попадает в реестр. "
            "Введите ID анкеты получателя.",
            keyboard=cancel(),
        )
        return

    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD_MODE, card_type=card_type.name
    )
    await message.answer(
        f"Тип: {card_type.value}. Как заполняем карту?",
        keyboard=card_add_mode_menu(),
    )


@labeler.message(state=AdminCardState.ORDINARY_CHARACTER)
async def choose_ordinary_character(message: Message, **_: object) -> None:
    try:
        character_id = parse_positive_int(message.text, field="ID анкеты")
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.ORDINARY_QUANTITY,
        card_type=CardType.ORDINARY.name,
        character_id=character_id,
    )
    await message.answer(
        f"Обычная карта для #{character.id} · {character.name}. "
        "Сколько одинаковых копий добавить?",
        keyboard=cancel(),
    )


@labeler.message(state=AdminCardState.ORDINARY_QUANTITY)
async def choose_ordinary_quantity(message: Message, **_: object) -> None:
    try:
        quantity = parse_positive_int(message.text, field="Количество карт")
        if quantity > card_service.MAX_CARD_QUANTITY:
            raise ValidationError(
                f"За один раз можно добавить не больше "
                f"{card_service.MAX_CARD_QUANTITY} копий."
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    payload = dict(message.state_peer.payload)
    payload["quantity"] = quantity
    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD_MODE, **payload
    )
    await message.answer(
        f"Количество: {quantity}. Как заполняем карту?",
        keyboard=card_add_mode_menu(),
    )


@labeler.message(payload={"cmd": "admin_card_add_template"})
async def choose_template_mode(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_MODE)
    if payload is None:
        return
    card_type = parse_card_type(str(payload["card_type"]))
    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD_TEMPLATE, **payload
    )
    await message.answer(template_for(card_type), keyboard=cancel())


@labeler.message(payload={"cmd": "admin_card_add_wizard"})
async def choose_wizard_mode(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_MODE)
    if payload is None:
        return
    await state_dispenser.set(message.peer_id, AdminCardState.ADD_NAME, **payload)
    await message.answer("Пришлите название карты.", keyboard=cancel())


@labeler.message(payload={"cmd": "admin_card_add_ai"})
async def choose_ai_mode(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_MODE)
    if payload is None:
        return
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.ADD_AI_SOURCE,
        **payload,
        source_parts=[],
    )
    await message.answer(
        "Опишите карту своими словами или пришлите заполненный текст в любом "
        "формате. Можно отправить несколько сообщений. Когда закончите, нажмите "
        "«Готово — обработать».",
        keyboard=ai_collect_menu("admin_ai_card"),
    )


@labeler.message(payload={"cmd": "admin_ai_card_generate"})
async def generate_ai_card(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_AI_SOURCE)
    if payload is None:
        return
    source_parts = list(payload.get("source_parts", []))
    if not source_parts:
        await message.answer(
            "Сначала пришлите описание карты.",
            keyboard=ai_collect_menu("admin_ai_card"),
        )
        return
    card_type = parse_card_type(str(payload["card_type"]))
    await message.answer("Оформляю карту…", keyboard=cancel())
    try:
        draft = await ai_service.generate_card("\n\n".join(source_parts), card_type)
    except ServiceError as error:
        await message.answer(
            str(error), keyboard=ai_collect_menu("admin_ai_card")
        )
        return
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.ADD_AI_CONFIRM,
        card_type=card_type.name,
        character_id=payload.get("character_id"),
        quantity=payload.get("quantity", 1),
        draft=draft.model_dump(mode="json"),
    )
    await answer_long(
        message,
        ai_service.card_preview(draft, card_type),
        keyboard=ai_confirm_menu("admin_ai_card"),
    )


@labeler.message(state=AdminCardState.ADD_AI_SOURCE)
async def collect_ai_card_source(message: Message, **_: object) -> None:
    text = message.text.strip()
    if not text:
        await message.answer(
            "Пришлите текстовое описание карты.",
            keyboard=ai_collect_menu("admin_ai_card"),
        )
        return
    payload = dict(message.state_peer.payload)
    source_parts = list(payload.get("source_parts", []))
    source_parts.append(text)
    payload["source_parts"] = source_parts
    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD_AI_SOURCE, **payload
    )
    await message.answer(
        f"Добавлено фрагментов: {len(source_parts)}. Можно продолжить или обработать.",
        keyboard=ai_collect_menu("admin_ai_card"),
    )


@labeler.message(payload={"cmd": "admin_ai_card_confirm"})
async def confirm_ai_card(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_AI_CONFIRM)
    if payload is None:
        return
    draft = ai_service.CardDraft.model_validate(payload["draft"])
    wizard_payload: dict[str, object] = {
        "card_type": payload["card_type"],
        "character_id": payload.get("character_id"),
        "quantity": payload.get("quantity", 1),
        "name": draft.name,
        "kind": draft.kind,
        "rarity": draft.rarity.name,
        "description": draft.description,
        "usage": draft.usage,
        "ai_complete": True,
    }
    card_type = parse_card_type(str(payload["card_type"]))
    if card_type is CardType.SPECIAL:
        await state_dispenser.set(
            message.peer_id, AdminCardState.ADD_NUMBER, **wizard_payload
        )
        await message.answer(
            "AI-карточка готова. Теперь укажите номер Особого слота от 0 до 99.",
            keyboard=cancel(),
        )
        return
    await _create_wizard_card(message, wizard_payload)
