from collections import defaultdict

from vkbottle.bot import BotLabeler, Message
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

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True

CARD_PAGE_SIZE = 6
FIELD_TITLES = dict(FIELDS)


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
        card_id = _positive_payload(
            message.get_payload_json() or {}, "card_id", "ID карты"
        )
        selected = list(state.payload.get("selected_ownership_ids", []))
        if len(selected) >= int(state.payload.get("max_components", 2)):
            raise ValidationError(
                "В выбранный размер Контура больше карт не помещается."
            )
        async with get_session() as session:
            ownership = await cards_crud.get_free_ownership(
                session, card_id, state.payload["character_id"]
            )
            if ownership is None:
                raise ValidationError("Свободной копии этой карты больше нет.")
            selected_ownerships = [
                await cards_crud.get_ownership_by_id(session, item) for item in selected
            ]
            if any(item and item.card_id == card_id for item in selected_ownerships):
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
            if not any(item.card.card_type is CardType.CONTOUR for item in ownerships):
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
        await message.answer(
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
    await message.answer(
        formatters.format_contour(contour),
        keyboard=contour_components_actions_menu(contour),
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
    await message.answer(
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
    await message.answer(
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
    await message.answer(
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
    await message.answer(
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
    await message.answer(
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


async def _show_create_component_picker(message: Message, requested_page: int) -> None:
    state = await _require_state(message, AdminContourState.CREATE_COMPONENTS)
    if state is None:
        return
    selected_ids = list(state.payload.get("selected_ownership_ids", []))
    async with get_session() as session:
        ownerships = await cards_crud.list_character_ownerships(
            session, state.payload["character_id"]
        )
        selected_card_ids = {
            ownership.card_id for ownership in ownerships if ownership.id in selected_ids
        }
        grouped = _free_groups(ownerships, excluded_card_ids=selected_card_ids)
        page, pages = normalize_page(
            requested_page, len(grouped), page_size=CARD_PAGE_SIZE
        )
        chunk = grouped[page * CARD_PAGE_SIZE : (page + 1) * CARD_PAGE_SIZE]
        selected_names = [
            ownership.card.name for ownership in ownerships if ownership.id in selected_ids
        ]
    maximum = int(state.payload.get("max_components", 2))
    text = (
        f"Выберите от 2 до {maximum} разных свободных карт. Минимум одна должна "
        "быть Контурной.\n"
        + (
            "Новый Контур начинает с размера 2; размер можно прокачать после создания.\n\n"
            if state.payload.get("mode") == "create"
            else "\n"
        )
        + "Выбрано: "
        + (" + ".join(selected_names) if selected_names else "ничего")
    )
    await message.answer(
        text,
        keyboard=contour_create_components_menu(
            [(card_id, name, count) for card_id, _, name, count in chunk],
            selected_count=len(selected_ids),
            page=page,
            pages=pages,
        ),
    )


async def _show_current_component_picker(
    message: Message, text: str, action: str
) -> None:
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
        text, keyboard=contour_current_component_menu(contour, action)
    )


async def _show_action_page(message: Message, *, mode: str) -> None:
    expected = (
        AdminContourState.ADD_COMPONENT
        if mode == "add"
        else AdminContourState.REPLACE_COMPONENT
    )
    state = await _require_state(message, expected)
    if state is None:
        return
    try:
        page = int((message.get_payload_json() or {}).get("page", 0))
    except (TypeError, ValueError):
        page = 0
    async with get_session() as session:
        contour = await contour_service.require_visible_contour(
            session,
            contour_id=state.payload["contour_id"],
            viewer_vk_id=message.from_id,
        )
    await _show_available_cards(message, contour, page, mode=mode)


async def _show_available_cards(
    message: Message, contour: Contour, requested_page: int, *, mode: str
) -> None:
    async with get_session() as session:
        ownerships = await cards_crud.list_character_ownerships(
            session, contour.character_id
        )
        excluded = {component.ownership.card_id for component in contour.components}
        grouped = _free_groups(ownerships, excluded_card_ids=excluded)
        page, pages = normalize_page(
            requested_page, len(grouped), page_size=CARD_PAGE_SIZE
        )
        chunk = grouped[page * CARD_PAGE_SIZE : (page + 1) * CARD_PAGE_SIZE]
    command = (
        "admin_contour_card_add_select"
        if mode == "add"
        else "admin_contour_card_replace_select"
    )
    text = "Выберите свободную карту:" if chunk else "Подходящих свободных карт нет."
    await message.answer(
        text,
        keyboard=contour_available_cards_menu(
            [(ownership_id, name, count) for _, ownership_id, name, count in chunk],
            command=command,
            target_id=contour.id,
            page=page,
            pages=pages,
        ),
    )


def _free_groups(
    ownerships: list[CardOwnership], *, excluded_card_ids: set[int]
) -> list[tuple[int, int, str, int]]:
    grouped: dict[int, list[CardOwnership]] = defaultdict(list)
    for ownership in ownerships:
        if ownership.contour_component is None and ownership.card_id not in excluded_card_ids:
            grouped[ownership.card_id].append(ownership)
    return [
        (card_id, items[0].id, items[0].card.name, len(items))
        for card_id, items in grouped.items()
    ]


async def _start_ai(
    message: Message,
    *,
    mode: str,
    character_id: int,
    ownership_ids: list[int],
    base_payload: dict[str, object],
) -> None:
    async with get_session() as session:
        character = await characters_crud.get_by_id(session, character_id)
        if character is None:
            await message.answer("Анкета не найдена.", keyboard=cancel())
            return
        ownerships = [
            await cards_crud.get_ownership_by_id(session, item) for item in ownership_ids
        ]
        if any(item is None for item in ownerships):
            await message.answer("Одна из выбранных карт больше недоступна.", keyboard=cancel())
            return
        character_context = _character_context(character)
        card_context = _card_context(ownerships)
    await state_dispenser.set(
        message.peer_id,
        AdminContourState.AI_SOURCE,
        **{
            **base_payload,
            "mode": mode,
            "character_id": character_id,
            "ownership_ids": ownership_ids,
            "character_context": character_context,
            "card_context": card_context,
            "source_parts": [],
            "image_urls": [],
        },
    )
    await message.answer(
        "Присылайте идею или черновик несколькими сообщениями. Можно приложить "
        "изображение внешнего вида. AI не сможет изменить выбранные карты.",
        keyboard=contour_ai_collect_menu(),
    )


async def _create_from_fields(session, payload, fields, admin_vk_id: int) -> Contour:
    data = dict(fields)
    name = str(data.pop("name", ""))
    return await contour_service.create_contour(
        session,
        character_id=payload["character_id"],
        ownership_ids=list(payload["selected_ownership_ids"]),
        slot=payload["slot"],
        name=name,
        admin_vk_id=admin_vk_id,
        **data,
    )


async def _require_state(message: Message, expected: str):
    state = await state_dispenser.get(message.peer_id)
    # StateRepresentation в vkbottle определяет __eq__ и __ne__ несогласованно:
    # для одного состояния оба оператора могут вернуть True. Сравниваем только
    # через положительный __eq__, как это делает рабочий AI-роутер.
    if state is None or not state.state == expected:
        await message.answer(
            "Сценарий устарел или был отменён.", keyboard=back_to_admin_characters()
        )
        return None
    return state


async def contours_component(session, component_id: int):
    from bot.database.crud import contours as contours_crud

    component = await contours_crud.get_component(session, component_id)
    if component is None:
        raise ValidationError("Компонент Контура не найден.")
    return component


def _positive_payload(
    payload: dict[str, object], key: str, field: str
) -> int:
    return parse_positive_int(str(payload.get(key, "")), field=field)


def _payload_id(message: Message, field: str) -> int:
    return _positive_payload(message.get_payload_json() or {}, "id", field)


def _character_context(character) -> str:
    return "\n".join(
        value
        for value in (
            f"Имя: {character.name}",
            f"Характер: {character.personality}",
            f"Биография: {character.biography}",
            f"Навыки: {character.skills}",
            f"Дополнительно: {character.additional}",
        )
        if not value.endswith(": ")
    )


def _card_context(ownerships: list[CardOwnership]) -> str:
    return "\n\n".join(
        f"Карта #{ownership.card.id}: {ownership.card.name}\n"
        f"Тип: {ownership.card.card_type.value}\n"
        f"Подтип/вид: {ownership.card.kind}\n"
        f"Описание: {ownership.card.description}\n"
        f"Использование: {ownership.card.usage}"
        for ownership in ownerships
    )


def _photo_urls(message: Message) -> list[str]:
    urls: list[str] = []
    for photo in message.get_photo_attachments() or []:
        sizes = [size for size in (photo.sizes or []) if size.url]
        original = getattr(photo, "orig_photo", None)
        if original is not None and original.url:
            sizes.append(original)
        if sizes:
            largest = max(sizes, key=lambda size: size.width * size.height)
            urls.append(largest.url)
        elif photo.photo_256:
            urls.append(photo.photo_256)
    return urls


def _back_to_contours(character_id: int) -> str:
    from vkbottle import Keyboard, KeyboardButtonColor, Text

    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "К Контурам",
            payload={"cmd": "character_contours", "id": character_id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()
