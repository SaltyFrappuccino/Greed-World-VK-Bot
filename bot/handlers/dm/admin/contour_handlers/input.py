from vkbottle.bot import Message

from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.engine import get_session
from bot.database.models import CardOwnership, CardType, Contour
from bot.keyboards.admin_menu import (
    back_to_admin_characters,
    contour_ai_collect_menu,
    contour_ai_confirm_menu,
    contour_available_cards_menu,
    contour_components_actions_menu,
    contour_create_components_menu,
    contour_create_mode_menu,
    contour_current_component_menu,
    contour_delete_confirm_menu,
    contour_fields_menu,
)
from bot.keyboards.main_menu import cancel, contour_detail_menu
from bot.middlewares.auth import AdminRule
from bot.services import ai_service, contour_service
from bot.services.contour_template_service import (
    CONTOUR_TEMPLATE,
    FIELDS,
    parse_contour_template,
)
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminContourState, clear_state, state_dispenser
from bot.utils import formatters
from bot.utils.pagination import normalize_page
from bot.utils.validators import parse_positive_int
from bot.handlers.dm.admin.contour_handlers.routing import labeler
from bot.handlers.dm.admin.contour_handlers.support import (
    FIELD_TITLES,
    _back_to_contours,
    _card_context,
    _character_context,
    _create_from_fields,
    _payload_id,
    _positive_payload,
    _require_state,
    _show_action_page,
    _show_available_cards,
    _show_create_component_picker,
    _show_current_component_picker,
    _start_ai,
    contours_component,
)

@labeler.message(state=AdminContourState.CREATE_MANUAL)
async def collect_manual_field(message: Message, **_: object) -> None:
    state = message.state_peer
    index = int(state.payload["field_index"])
    field, title = FIELDS[index]
    value = message.text.strip()
    if field == "name" and not value:
        await message.answer("Название не может быть пустым.", keyboard=cancel())
        return
    draft = dict(state.payload.get("draft", {}))
    draft[field] = "" if value == "-" else value
    next_index = index + 1
    if next_index < len(FIELDS):
        next_field, next_title = FIELDS[next_index]
        await state_dispenser.set(
            message.peer_id,
            AdminContourState.CREATE_MANUAL,
            **{**state.payload, "field_index": next_index, "draft": draft},
        )
        hint = " Для пустого значения пришлите «-»." if next_field != "name" else ""
        await message.answer(
            f"Теперь заполните поле «{next_title}».{hint}", keyboard=cancel()
        )
        return
    try:
        async with get_session() as session:
            contour = await _create_from_fields(
                session, state.payload, draft, message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        "Контур создан.\n\n" + formatters.format_contour(contour),
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(state=AdminContourState.CREATE_TEMPLATE)
async def save_template(message: Message, **_: object) -> None:
    try:
        fields = parse_contour_template(message.text)
        async with get_session() as session:
            contour = await _create_from_fields(
                session, message.state_peer.payload, fields, message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        "Контур создан.\n\n" + formatters.format_contour(contour),
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(state=AdminContourState.CAPACITY_VALUE)
async def set_capacity(message: Message, **_: object) -> None:
    try:
        value = parse_positive_int(message.text, field="Размер Контура")
        async with get_session() as session:
            contour = await contour_service.set_capacity(
                session,
                contour_id=message.state_peer.payload["contour_id"],
                value=value,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Размер Контура установлен: {contour.card_capacity}.",
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(state=AdminContourState.LIMIT_VALUE)
async def set_character_limit(message: Message, **_: object) -> None:
    try:
        value = parse_positive_int(message.text, field="Лимит Контуров")
        async with get_session() as session:
            character = await contour_service.set_character_limit(
                session,
                character_id=message.state_peer.payload["character_id"],
                value=value,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Лимит Контуров персонажа #{character.id} · {character.name}: {value}.",
        keyboard=back_to_admin_characters(),
    )


@labeler.message(state=AdminContourState.EDIT_VALUE)
async def save_field(message: Message, **_: object) -> None:
    state = message.state_peer
    value = message.text.strip()
    if state.payload["field"] == "name" and (not value or value == "-"):
        await message.answer("Название не может быть пустым.", keyboard=cancel())
        return
    try:
        async with get_session() as session:
            contour = await contour_service.update_contour(
                session,
                contour_id=state.payload["contour_id"],
                admin_vk_id=message.from_id,
                **{state.payload["field"]: "" if value == "-" else value},
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await message.answer(
        "Поле обновлено.\n\n" + formatters.format_contour(contour),
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(state=AdminContourState.AI_SOURCE)
async def collect_ai_source(message: Message, **_: object) -> None:
    state = message.state_peer
    source_parts = list(state.payload.get("source_parts", []))
    image_urls = list(state.payload.get("image_urls", []))
    text = message.text.strip()
    photos = _photo_urls(message)
    if not text and not photos:
        await message.answer(
            "В сообщении нет текста или изображения.",
            keyboard=contour_ai_collect_menu(),
        )
        return
    if text:
        source_parts.append(text)
    image_urls.extend(url for url in photos if url not in image_urls)
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.AI_SOURCE,
        **{
            **state.payload,
            "source_parts": source_parts,
            "image_urls": image_urls,
        },
    )
    await message.answer(
        f"Добавлено: сообщений — {len(source_parts)}, изображений — {len(image_urls)}.",
        keyboard=contour_ai_collect_menu(),
    )


