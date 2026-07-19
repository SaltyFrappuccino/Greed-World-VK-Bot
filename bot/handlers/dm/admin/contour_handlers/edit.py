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
from bot.utils.messages import answer_long
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

@labeler.message(payload_contains={"cmd": "admin_contour_fields"})
async def show_fields(message: Message, **_: object) -> None:
    try:
        contour_id = _payload_id(message, "ID Контура")
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await clear_state(message.peer_id)
    await message.answer(
        "Какое поле изменить?", keyboard=contour_fields_menu(contour_id)
    )


@labeler.message(payload_contains={"cmd": "admin_contour_field_select"})
async def select_field(message: Message, **_: object) -> None:
    payload = message.get_payload_json() or {}
    field = str(payload.get("field", ""))
    if field not in FIELD_TITLES:
        await message.answer("Это поле редактировать нельзя.")
        return
    try:
        contour_id = _positive_payload(payload, "id", "ID Контура")
        async with get_session() as session:
            contour = await contour_service.require_visible_contour(
                session, contour_id=contour_id, viewer_vk_id=message.from_id
            )
            current = str(getattr(contour, field))
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.EDIT_VALUE,
        contour_id=contour_id,
        field=field,
    )
    await message.answer(
        f"Поле: {FIELD_TITLES[field]}\nСейчас: {current or '—'}\n\n"
        "Пришлите новое значение. Для очистки — «-».",
        keyboard=cancel(),
    )


@labeler.message(payload_contains={"cmd": "admin_contour_components"})
async def show_components(message: Message, **_: object) -> None:
    try:
        contour_id = _payload_id(message, "ID Контура")
        async with get_session() as session:
            contour = await contour_service.require_visible_contour(
                session, contour_id=contour_id, viewer_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await clear_state(message.peer_id)
    await answer_long(
        message, formatters.format_contour(contour), keyboard=contour_components_actions_menu(contour)
    )


@labeler.message(payload_contains={"cmd": "admin_contour_card_add"})
async def start_add_card(message: Message, **_: object) -> None:
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
        message.peer_id, AdminContourState.ADD_COMPONENT, contour_id=contour.id
    )
    await _show_available_cards(message, contour, 0, mode="add")


@labeler.message(payload_contains={"cmd": "admin_contour_card_add_select_page"})
async def add_card_page(message: Message, **_: object) -> None:
    await _show_action_page(message, mode="add")


@labeler.message(payload_contains={"cmd": "admin_contour_card_add_select"})
async def add_card_select(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.ADD_COMPONENT)
    if state is None:
        return
    try:
        ownership_id = _positive_payload(
            message.get_payload_json() or {}, "ownership_id", "ID копии"
        )
        async with get_session() as session:
            contour = await contour_service.add_card(
                session,
                contour_id=state.payload["contour_id"],
                ownership_id=ownership_id,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await answer_long(
        message,
        "Карта добавлена.\n\n" + formatters.format_contour(contour),
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_contour_card_remove"})
async def choose_remove_card(message: Message, **_: object) -> None:
    await _show_current_component_picker(
        message, "Какую карту убрать?", "admin_contour_card_remove_confirm"
    )


@labeler.message(payload_contains={"cmd": "admin_contour_card_remove_confirm"})
async def remove_card(message: Message, **_: object) -> None:
    try:
        component_id = _positive_payload(
            message.get_payload_json() or {}, "component_id", "ID компонента"
        )
        async with get_session() as session:
            contour = await contour_service.remove_card(
                session, component_id=component_id, admin_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await answer_long(
        message,
        "Карта освобождена.\n\n" + formatters.format_contour(contour),
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_contour_card_replace"})
async def choose_replace_card(message: Message, **_: object) -> None:
    await _show_current_component_picker(
        message, "Какую карту заменить?", "admin_contour_card_replace_pick"
    )


@labeler.message(payload_contains={"cmd": "admin_contour_card_replace_pick"})
async def pick_replaced_component(message: Message, **_: object) -> None:
    try:
        component_id = _positive_payload(
            message.get_payload_json() or {}, "component_id", "ID компонента"
        )
        async with get_session() as session:
            component = await contours_component(session, component_id)
            contour = await contour_service.require_visible_contour(
                session,
                contour_id=component.contour_id,
                viewer_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.REPLACE_COMPONENT,
        contour_id=contour.id,
        component_id=component_id,
    )
    await _show_available_cards(message, contour, 0, mode="replace")


@labeler.message(payload_contains={"cmd": "admin_contour_card_replace_select_page"})
async def replace_card_page(message: Message, **_: object) -> None:
    await _show_action_page(message, mode="replace")


@labeler.message(payload_contains={"cmd": "admin_contour_card_replace_select"})
async def replace_card_select(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.REPLACE_COMPONENT)
    if state is None:
        return
    try:
        ownership_id = _positive_payload(
            message.get_payload_json() or {}, "ownership_id", "ID копии"
        )
        async with get_session() as session:
            contour = await contour_service.replace_card(
                session,
                component_id=state.payload["component_id"],
                ownership_id=ownership_id,
                admin_vk_id=message.from_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await answer_long(
        message,
        "Карта заменена.\n\n" + formatters.format_contour(contour),
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_contour_ai"})
async def start_edit_ai(message: Message, **_: object) -> None:
    try:
        contour_id = _payload_id(message, "ID Контура")
        async with get_session() as session:
            contour = await contour_service.require_visible_contour(
                session, contour_id=contour_id, viewer_vk_id=message.from_id
            )
            if not contour.components:
                raise ValidationError("Сначала привяжите реальные карты к Контуру.")
            ownership_ids = [
                component.card_ownership_id for component in contour.components
            ]
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await _start_ai(
        message,
        mode="edit",
        character_id=contour.character_id,
        ownership_ids=ownership_ids,
        base_payload={"contour_id": contour.id},
    )


@labeler.message(payload={"cmd": "admin_contour_ai_generate"})
async def generate_ai(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.AI_SOURCE)
    if state is None:
        return
    source_parts = list(state.payload.get("source_parts", []))
    image_urls = list(state.payload.get("image_urls", []))
    if not source_parts and not image_urls:
        await message.answer(
            "Сначала пришлите идею, черновик или изображение.",
            keyboard=contour_ai_collect_menu(),
        )
        return
    await message.answer("Прорабатываю описание Контура…", keyboard=cancel())
    try:
        draft = await ai_service.generate_contour(
            "\n\n".join(source_parts),
            state.payload["character_context"],
            state.payload["card_context"],
            image_urls=image_urls,
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=contour_ai_collect_menu())
        return
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.AI_CONFIRM,
        **state.payload,
        draft=draft.model_dump(),
    )
    await answer_long(
        message,
        ai_service.contour_preview(draft)
        + "\n\nСостав останется без изменений:\n"
        + state.payload["card_context"],
        keyboard=contour_ai_confirm_menu(),
    )


@labeler.message(payload={"cmd": "admin_contour_ai_confirm"})
async def confirm_ai(message: Message, **_: object) -> None:
    state = await _require_state(message, AdminContourState.AI_CONFIRM)
    if state is None:
        return
    try:
        draft = ai_service.ContourDraft.model_validate(state.payload["draft"])
        fields = ai_service.contour_fields(draft)
        async with get_session() as session:
            if state.payload["mode"] == "edit":
                contour = await contour_service.update_contour(
                    session,
                    contour_id=state.payload["contour_id"],
                    admin_vk_id=message.from_id,
                    **fields,
                )
            else:
                contour = await _create_from_fields(
                    session, state.payload, fields, message.from_id
                )
    except (ServiceError, ValueError) as error:
        await message.answer(str(error), keyboard=cancel())
        return
    await clear_state(message.peer_id)
    await answer_long(
        message,
        "Контур сохранён.\n\n" + formatters.format_contour(contour),
        keyboard=contour_detail_menu(contour, is_admin=True),
    )


@labeler.message(payload_contains={"cmd": "admin_contour_delete"})
async def confirm_disassemble(message: Message, **_: object) -> None:
    try:
        contour_id = _payload_id(message, "ID Контура")
        async with get_session() as session:
            contour = await contour_service.require_visible_contour(
                session, contour_id=contour_id, viewer_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await message.answer(
        f"Разобрать Контур #{contour.id} · {contour.name}? Все его карты "
        "останутся у персонажа и снова станут свободными.",
        keyboard=contour_delete_confirm_menu(contour.id),
    )


@labeler.message(payload_contains={"cmd": "admin_contour_delete_confirm"})
async def disassemble(message: Message, **_: object) -> None:
    try:
        contour_id = _payload_id(message, "ID Контура")
        async with get_session() as session:
            character_id, name = await contour_service.disassemble(
                session, contour_id=contour_id, admin_vk_id=message.from_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_characters())
        return
    await clear_state(message.peer_id)
    await message.answer(
        f"Контур «{name}» разобран. Карты освобождены.",
        keyboard=_back_to_contours(character_id),
    )


