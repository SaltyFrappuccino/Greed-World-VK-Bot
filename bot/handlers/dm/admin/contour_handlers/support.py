from collections import defaultdict

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

CARD_PAGE_SIZE = 6
FIELD_TITLES = dict(FIELDS)


async def _show_create_component_picker(message: Message, requested_page: int) -> None:
    state = await _require_state(message, AdminContourState.CREATE_COMPONENTS)
    if state is None:
        return
    selected_ids = list(state.payload.get("selected_ownership_ids", []))
    async with get_session() as session:
        ownerships = await cards_crud.list_character_ownerships(
            session, state.payload["character_id"]
        )
        selected_card_keys = {
            (ownership.display_type, ownership.display_name.casefold())
            for ownership in ownerships
            if ownership.id in selected_ids
        }
        grouped = _free_groups(ownerships, excluded_card_keys=selected_card_keys)
        page, pages = normalize_page(
            requested_page, len(grouped), page_size=CARD_PAGE_SIZE
        )
        chunk = grouped[page * CARD_PAGE_SIZE : (page + 1) * CARD_PAGE_SIZE]
        selected_names = [
            ownership.display_name for ownership in ownerships if ownership.id in selected_ids
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
            [(ownership_id, name, count) for _, ownership_id, name, count in chunk],
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
        excluded = {
            (
                component.ownership.display_type,
                component.ownership.display_name.casefold(),
            )
            for component in contour.components
        }
        grouped = _free_groups(ownerships, excluded_card_keys=excluded)
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
    ownerships: list[CardOwnership],
    *,
    excluded_card_keys: set[tuple[CardType, str]],
) -> list[tuple[tuple[CardType, str], int, str, int]]:
    grouped: dict[tuple[CardType, str], list[CardOwnership]] = defaultdict(list)
    for ownership in ownerships:
        key = (ownership.display_type, ownership.display_name.casefold())
        if ownership.contour_component is None and key not in excluded_card_keys:
            grouped[key].append(ownership)
    return [
        (key, items[0].id, items[0].display_name, len(items))
        for key, items in grouped.items()
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
        f"Карта: {ownership.display_name}\n"
        f"Тип: {ownership.display_type.value}\n"
        f"Подтип/вид: {ownership.display_kind}\n"
        f"Описание: {ownership.display_description}\n"
        f"Использование: {ownership.display_usage}"
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
