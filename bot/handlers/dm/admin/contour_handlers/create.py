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
from bot.utils.messages import answer_long
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

@labeler.message(payload_contains={"cmd": "admin_contour_create"})
async def start_create(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    try:
        character_id = _positive_payload(payload, "character_id", "ID анкеты")
        slot = _positive_payload(payload, "slot", "Слот")
        async with get_session() as session:
            character = await characters_crud.get_by_id(session, character_id)
            if character is None:
                raise ValidationError("Анкета не найдена.")
            if slot > character.contour_limit:
                raise ValidationError("Этот слот больше недоступен анкете.")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return

    await state_dispenser.set(
        message.peer_id,
        AdminContourState.CREATE_COMPONENTS,
        mode="create",
        character_id=character_id,
        slot=slot,
        max_components=2,
        selected_ownership_ids=[],
    )
    await _show_create_component_picker(message, 0)


@labeler.message(payload_contains={"cmd": "admin_contour_cards_rebuild"})
async def start_rebuild(message: Message, **_: object) -> None:
    try:
        contour_id = _payload_id(message, "ID Контура")
        async with get_session() as session:
            contour = await contour_service.require_visible_contour(
                session, contour_id=contour_id, viewer_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.CREATE_COMPONENTS,
        mode="rebuild",
        contour_id=contour.id,
        character_id=contour.character_id,
        max_components=contour.card_capacity,
        selected_ownership_ids=[],
    )
    await _show_create_component_picker(message, 0)


@labeler.message(payload_contains={"cmd": "admin_contour_components_create_page"})
async def create_components_page(message: Message, **_: object) -> None:
    try:
        page = int((message.get_payload_json() or {}).get("page", 0))
    except (TypeError, ValueError):
        page = 0
    await _show_create_component_picker(message, page)


@labeler.message(payload_contains={"cmd": "admin_contour_component_select"})
async def select_create_component(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.CREATE_COMPONENTS)
    if state is None:
        return
    try:
        ownership_id = _positive_payload(
            message.get_payload_json() or {}, "ownership_id", "ID копии карты"
        )
        selected = list(state.payload.get("selected_ownership_ids", []))
        if len(selected) >= int(state.payload.get("max_components", 2)):
            raise ValidationError(
                "В выбранный размер Контура больше карт не помещается."
            )
        async with get_session() as session:
            ownership = await cards_crud.get_ownership_by_id(session, ownership_id)
            if (
                ownership is None
                or ownership.character_id != state.payload["character_id"]
                or ownership.contour_component is not None
            ):
                raise ValidationError("Свободной копии этой карты больше нет.")
            selected_ownerships = [
                await cards_crud.get_ownership_by_id(session, item) for item in selected
            ]
            if any(
                item
                and item.display_type is ownership.display_type
                and item.display_name.casefold() == ownership.display_name.casefold()
                for item in selected_ownerships
            ):
                raise ValidationError("Две одинаковые карты в Контуре запрещены.")
            selected.append(ownership.id)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.CREATE_COMPONENTS,
        **{**state.payload, "selected_ownership_ids": selected},
    )
    await _show_create_component_picker(message, 0)


@labeler.message(payload={"cmd": "admin_contour_components_ready"})
async def finish_component_selection(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.CREATE_COMPONENTS)
    if state is None:
        return
    selected = list(state.payload.get("selected_ownership_ids", []))
    try:
        async with get_session() as session:
            ownerships = [
                await cards_crud.get_ownership_by_id(session, item) for item in selected
            ]
            if len(ownerships) < 2 or any(item is None for item in ownerships):
                raise ValidationError("Выберите минимум две доступные карты.")
            if not any(item.display_type is CardType.CONTOUR for item in ownerships):
                raise ValidationError(
                    "В составе должна быть хотя бы одна Контурная карта."
                )
            if state.payload.get("mode") == "rebuild":
                contour = await contour_service.set_cards(
                    session,
                    contour_id=state.payload["contour_id"],
                    ownership_ids=selected,
                    admin_vk_id=message.from_id,
                )
            else:
                contour = None
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    if contour is not None:
        await clear_state(message.peer_id)
        await answer_long(
            message,
            "Состав привязан.\n\n" + formatters.format_contour(contour),
            keyboard=contour_detail_menu(contour, is_admin=True),
        )
        return
    await state_dispenser.set(
        message.peer_id, AdminContourState.CREATE_MODE, **state.payload
    )
    await message.answer(
        "Состав зафиксирован. Как заполнить описание Контура?",
        keyboard=contour_create_mode_menu(),
    )


@labeler.message(payload={"cmd": "admin_contour_mode_manual"})
async def start_manual(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.CREATE_MODE)
    if state is None:
        return
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.CREATE_MANUAL,
        **state.payload,
        field_index=0,
        draft={},
    )
    await message.answer("Пришлите название Контура.", keyboard=cancel())


@labeler.message(payload={"cmd": "admin_contour_mode_template"})
async def start_template(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.CREATE_MODE)
    if state is None:
        return
    await state_dispenser.set(
        message.peer_id, AdminContourState.CREATE_TEMPLATE, **state.payload
    )
    await message.answer(CONTOUR_TEMPLATE, keyboard=cancel())


@labeler.message(payload={"cmd": "admin_contour_mode_ai"})
async def start_create_ai(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.CREATE_MODE)
    if state is None:
        return
    await _start_ai(
        message,
        mode="create",
        character_id=state.payload["character_id"],
        ownership_ids=list(state.payload["selected_ownership_ids"]),
        base_payload=state.payload,
    )


@labeler.message(payload_contains={"cmd": "admin_contour_capacity_up"})
async def upgrade_capacity(message: Message, **_: object) -> None:
    try:
        contour_id = _payload_id(message, "ID Контура")
        async with get_session() as session:
            contour = await contour_service.upgrade_capacity(
                session, contour_id=contour_id, admin_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await message.answer(
        f"Размер Контура увеличен до {contour.card_capacity} карт.",
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_contour_capacity_set"})
async def ask_capacity(message: Message, **_: object) -> None:
    try:
        contour_id = _payload_id(message, "ID Контура")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id, AdminContourState.CAPACITY_VALUE, contour_id=contour_id
    )
    await message.answer("Введите размер Контура от 2 до 5.", keyboard=cancel())


@labeler.message(payload_contains={"cmd": "admin_character_contour_limit_up"})
async def upgrade_character_limit(message: Message, **_: object) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
        async with get_session() as session:
            character = await contour_service.upgrade_character_limit(
                session,
                character_id=character_id,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await message.answer(
        f"Лимит Контуров персонажа #{character.id} · {character.name}: "
        f"{character.contour_limit}.",
        keyboard=back_to_admin_characters(),
    )


@labeler.message(payload_contains={"cmd": "admin_character_contour_limit_set"})
async def ask_character_limit(message: Message, **_: object) -> None:
    try:
        character_id = _payload_id(message, "ID анкеты")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.LIMIT_VALUE,
        character_id=character_id,
    )
    await message.answer(
        "Введите новый лимит количества Контуров (минимум 2).",
        keyboard=cancel(),
    )


