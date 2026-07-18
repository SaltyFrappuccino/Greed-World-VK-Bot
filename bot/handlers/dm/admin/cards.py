from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

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

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True

EDIT_HINT = """Пришлите правку одной строкой:

поле = значение

Поля: название, редкость, лимит, номер, описание, использование, подтип контура.
Пример: лимит = 5"""

# Ввод админа -> поле модели.
EDIT_FIELDS = {
    "название": "name",
    "вид": "kind",
    "подтип контура": "kind",
    "редкость": "rarity",
    "лимит": "transform_limit",
    "номер": "number",
    "описание": "description",
    "использование": "usage",
}


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
        AdminCardState.ADD_MODE,
        card_type=CardType.ORDINARY.name,
        character_id=character_id,
    )
    await message.answer(
        f"Обычная карта для #{character.id} · {character.name}. Как заполняем?",
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


@labeler.message(payload_contains={"cmd": "admin_card_contour_subtype"})
async def choose_contour_subtype(message: Message, **_: object) -> None:
    payload = await _wizard_payload(
        message, AdminCardState.ADD_CONTOUR_SUBTYPE
    )
    if payload is None:
        return
    subtype = str((message.get_payload_json() or {}).get("subtype", ""))
    if subtype not in CONTOUR_SUBTYPES:
        await message.answer(
            "Неизвестный подтип Контура.", keyboard=contour_subtype_menu()
        )
        return
    payload["kind"] = subtype
    await _ask_rarity(message, payload)


@labeler.message(payload_contains={"cmd": "admin_card_rarity"})
async def choose_rarity(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_RARITY)
    if payload is None:
        return
    try:
        rarity = parse_rarity(
            str((message.get_payload_json() or {}).get("rarity", ""))
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=card_rarity_menu())
        return
    payload["rarity"] = rarity.name
    card_type = parse_card_type(str(payload["card_type"]))
    if card_type is CardType.SPECIAL:
        await state_dispenser.set(
            message.peer_id, AdminCardState.ADD_NUMBER, **payload
        )
        await message.answer(
            "Пришлите номер Особого слота — целое число от 0 до 99.",
            keyboard=cancel(),
        )
    else:
        await _ask_description(message, payload)


@labeler.message(payload_contains={"cmd": "admin_card_limit"})
async def choose_special_limit(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_LIMIT)
    if payload is None:
        return
    value = (message.get_payload_json() or {}).get("limit")
    try:
        payload["transform_limit"] = (
            None
            if value == "none"
            else parse_positive_int(str(value), field="Лимит преобразований")
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=special_card_limit_menu())
        return
    if payload.get("ai_complete"):
        await _create_wizard_card(message, payload)
    else:
        await _ask_description(message, payload)


@labeler.message(payload={"cmd": "admin_card_limit_custom"})
async def ask_custom_special_limit(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_LIMIT)
    if payload is None:
        return
    await message.answer(
        "Пришлите целое число больше нуля.", keyboard=cancel()
    )


@labeler.message(payload={"cmd": "admin_card_description_skip"})
async def skip_description(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_DESCRIPTION)
    if payload is not None:
        await _after_description(message, payload, "")


@labeler.message(payload={"cmd": "admin_card_usage_skip"})
async def skip_usage(message: Message, **_: object) -> None:
    payload = await _wizard_payload(message, AdminCardState.ADD_USAGE)
    if payload is not None:
        payload["usage"] = ""
        await _create_wizard_card(message, payload)


@labeler.message(payload={"cmd": "admin_card_activation_skip"})
async def skip_spell_activation(message: Message, **_: object) -> None:
    payload = await _wizard_payload(
        message, AdminCardState.ADD_SPELL_ACTIVATION
    )
    if payload is not None:
        await _after_spell_activation(message, payload, "")


@labeler.message(payload={"cmd": "admin_card_consumption_skip"})
async def skip_spell_consumption(message: Message, **_: object) -> None:
    payload = await _wizard_payload(
        message, AdminCardState.ADD_SPELL_CONSUMPTION
    )
    if payload is not None:
        payload["consumption"] = ""
        await _create_spell_card(message, payload)


@labeler.message(state=AdminCardState.ADD_TEMPLATE)
async def do_add_template(message: Message, **_: object) -> None:
    state_payload = dict(message.state_peer.payload)
    character_id: int | None = None
    async with get_session() as session:
        try:
            card_type = parse_card_type(state_payload["card_type"])
            draft = parse_card_template(card_type, message.text)
            if card_type is CardType.ORDINARY:
                character_id = parse_positive_int(
                    str(state_payload.get("character_id", "")),
                    field="ID анкеты",
                )
                ownership = await card_service.grant_ordinary_card(
                    session,
                    character_id=character_id,
                    name=draft.name,
                    kind=draft.kind,
                    rarity=draft.rarity,
                    description=draft.description,
                    usage=draft.usage,
                )
                character = await characters_crud.get_by_id(session, character_id)
                text = (
                    f"Обычная карта «{ownership.display_name}» добавлена персонажу "
                    f"#{character.id} · {character.name}."
                )
            else:
                card = await card_service.create_card(
                    session,
                    name=draft.name,
                    card_type=draft.card_type,
                    kind=draft.kind,
                    rarity=draft.rarity,
                    transform_limit=draft.transform_limit,
                    number=draft.number,
                    description=draft.description,
                    usage=draft.usage,
                    admin_vk_id=message.from_id,
                )
                text = "Карта добавлена.\n\n" + formatters.card_full(card, live_copies=0)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    keyboard = (
        admin_character_cards_menu(character_id)
        if card_type is CardType.ORDINARY
        else back_to_admin_cards()
    )
    await message.answer(text, keyboard=keyboard)


@labeler.message(state=AdminCardState.ADD_NAME)
async def save_wizard_name(message: Message, **_: object) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым.", keyboard=cancel())
        return
    payload = dict(message.state_peer.payload)
    card_type = parse_card_type(str(payload["card_type"]))
    async with get_session() as session:
        if (
            card_type is not CardType.ORDINARY
            and await cards_crud.get_by_name(session, name) is not None
        ):
            await message.answer(
                f"Карта «{name}» уже есть в реестре. Пришлите другое название.",
                keyboard=cancel(),
            )
            return

    payload["name"] = name
    if card_type is CardType.CONTOUR:
        await state_dispenser.set(
            message.peer_id, AdminCardState.ADD_CONTOUR_SUBTYPE, **payload
        )
        await message.answer(
            "Выберите подтип Контурной карты:",
            keyboard=contour_subtype_menu(),
        )
    elif card_type is CardType.ORDINARY:
        await state_dispenser.set(
            message.peer_id, AdminCardState.ADD_KIND, **payload
        )
        await message.answer(
            "Что находится в карте? Например: предмет, оружие, еда, инструмент.",
            keyboard=cancel(),
        )
    else:
        payload["kind"] = card_type.value
        await _ask_rarity(message, payload)


@labeler.message(state=AdminCardState.ADD_KIND)
async def save_ordinary_kind(message: Message, **_: object) -> None:
    kind = message.text.strip()
    if not kind:
        await message.answer("Вид содержимого не может быть пустым.", keyboard=cancel())
        return
    payload = dict(message.state_peer.payload)
    payload["kind"] = kind
    await _ask_rarity(message, payload)


@labeler.message(state=AdminCardState.ADD_NUMBER)
async def save_special_number(message: Message, **_: object) -> None:
    try:
        number = parse_optional_slot_number(message.text)
        if number is None:
            raise ValidationError("У Особой карты номер слота обязателен.")
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return
    async with get_session() as session:
        if await cards_crud.get_by_number(session, number) is not None:
            await message.answer(
                f"Особый слот №{number} уже занят. Пришлите другой номер.",
                keyboard=cancel(),
            )
            return

    payload = dict(message.state_peer.payload)
    payload["number"] = number
    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD_LIMIT, **payload
    )
    await message.answer(
        "Выберите лимит преобразований:",
        keyboard=special_card_limit_menu(),
    )


@labeler.message(state=AdminCardState.ADD_LIMIT)
async def save_custom_special_limit(message: Message, **_: object) -> None:
    try:
        limit = parse_positive_int(message.text, field="Лимит преобразований")
    except ServiceError as error:
        await message.answer(str(error), keyboard=special_card_limit_menu())
        return
    payload = dict(message.state_peer.payload)
    payload["transform_limit"] = limit
    if payload.get("ai_complete"):
        await _create_wizard_card(message, payload)
    else:
        await _ask_description(message, payload)


@labeler.message(state=AdminCardState.ADD_DESCRIPTION)
async def save_wizard_description(message: Message, **_: object) -> None:
    await _after_description(
        message, dict(message.state_peer.payload), _optional_text(message.text)
    )


@labeler.message(state=AdminCardState.ADD_USAGE)
async def save_wizard_usage(message: Message, **_: object) -> None:
    payload = dict(message.state_peer.payload)
    payload["usage"] = _optional_text(message.text)
    await _create_wizard_card(message, payload)


@labeler.message(state=AdminCardState.ADD_SPELL_ACTIVATION)
async def save_spell_activation(message: Message, **_: object) -> None:
    await _after_spell_activation(
        message, dict(message.state_peer.payload), _optional_text(message.text)
    )


@labeler.message(state=AdminCardState.ADD_SPELL_CONSUMPTION)
async def save_spell_consumption(message: Message, **_: object) -> None:
    payload = dict(message.state_peer.payload)
    payload["consumption"] = _optional_text(message.text)
    await _create_spell_card(message, payload)


async def _wizard_payload(
    message: Message, expected_state: str
) -> dict[str, object] | None:
    state = await state_dispenser.get(message.peer_id)
    if state is None or not state.state == expected_state:
        await message.answer(
            "Этот сценарий создания карты уже завершён или отменён.",
            keyboard=back_to_admin_cards(),
        )
        return None
    return dict(state.payload)


async def _ask_rarity(message: Message, payload: dict[str, object]) -> None:
    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD_RARITY, **payload
    )
    await message.answer("Выберите редкость карты:", keyboard=card_rarity_menu())


async def _ask_description(
    message: Message, payload: dict[str, object]
) -> None:
    card_type = parse_card_type(str(payload["card_type"]))
    title = "описание эффекта" if card_type is CardType.SPELL else "описание"
    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD_DESCRIPTION, **payload
    )
    await message.answer(
        f"Пришлите {title} карты отдельным сообщением.",
        keyboard=skip_card_field_menu("admin_card_description_skip"),
    )


async def _after_description(
    message: Message, payload: dict[str, object], description: str
) -> None:
    payload["description"] = description
    card_type = parse_card_type(str(payload["card_type"]))
    if card_type is CardType.SPELL:
        await state_dispenser.set(
            message.peer_id, AdminCardState.ADD_SPELL_ACTIVATION, **payload
        )
        await message.answer(
            "Пришлите команду активации заклинания отдельным сообщением.",
            keyboard=skip_card_field_menu("admin_card_activation_skip"),
        )
    else:
        await state_dispenser.set(
            message.peer_id, AdminCardState.ADD_USAGE, **payload
        )
        await message.answer(
            "Пришлите способ использования карты отдельным сообщением.",
            keyboard=skip_card_field_menu("admin_card_usage_skip"),
        )


async def _after_spell_activation(
    message: Message, payload: dict[str, object], activation: str
) -> None:
    payload["activation"] = activation
    await state_dispenser.set(
        message.peer_id, AdminCardState.ADD_SPELL_CONSUMPTION, **payload
    )
    await message.answer(
        "Опишите расходование карты после применения.",
        keyboard=skip_card_field_menu("admin_card_consumption_skip"),
    )


async def _create_spell_card(
    message: Message, payload: dict[str, object]
) -> None:
    usage_parts = []
    activation = str(payload.get("activation", "")).strip()
    consumption = str(payload.get("consumption", "")).strip()
    if activation:
        usage_parts.append(f"Команда активации: {activation}")
    if consumption:
        usage_parts.append(f"Расходование: {consumption}")
    payload["usage"] = "\n".join(usage_parts)
    await _create_wizard_card(message, payload)


async def _create_wizard_card(
    message: Message, payload: dict[str, object]
) -> None:
    async with get_session() as session:
        try:
            card_type = parse_card_type(str(payload["card_type"]))
            if card_type is CardType.ORDINARY:
                character_id = parse_positive_int(
                    str(payload.get("character_id", "")), field="ID анкеты"
                )
                ownership = await card_service.grant_ordinary_card(
                    session,
                    character_id=character_id,
                    name=str(payload["name"]),
                    kind=str(payload["kind"]),
                    rarity=parse_rarity(str(payload["rarity"])),
                    description=str(payload.get("description", "")),
                    usage=str(payload.get("usage", "")),
                )
                character = await characters_crud.get_by_id(session, character_id)
                text = (
                    f"Обычная карта «{ownership.display_name}» добавлена персонажу "
                    f"#{character.id} · {character.name}."
                )
            else:
                card = await card_service.create_card(
                    session,
                    name=str(payload["name"]),
                    card_type=card_type,
                    kind=str(payload["kind"]),
                    rarity=parse_rarity(str(payload["rarity"])),
                    transform_limit=payload.get("transform_limit"),
                    number=payload.get("number"),
                    description=str(payload.get("description", "")),
                    usage=str(payload.get("usage", "")),
                    admin_vk_id=message.from_id,
                )
                text = "Карта добавлена.\n\n" + formatters.card_full(card, live_copies=0)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    keyboard = (
        admin_character_cards_menu(int(payload["character_id"]))
        if parse_card_type(str(payload["card_type"])) is CardType.ORDINARY
        else back_to_admin_cards()
    )
    await message.answer(text, keyboard=keyboard)


def _optional_text(value: str) -> str:
    value = value.strip()
    return "" if value == "-" else value


@labeler.message(payload={"cmd": "admin_card_edit"})
async def start_edit(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCardState.EDIT_PICK)
    await message.answer("Какую карту правим? Название или номер слота.", keyboard=cancel())


@labeler.message(payload_contains={"cmd": "admin_card_edit_select"})
async def select_edit_target(message: Message, **_: object) -> None:
    try:
        card_id = _payload_id(message)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return
    await _open_card_editor(message, card_id)


@labeler.message(state=AdminCardState.EDIT_PICK)
async def pick_edit_target(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            card = await card_service.find_card(session, message.text)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

        live_copies = await cards_crud.count_owners(session, card.id)
        card_id, text = card.id, formatters.card_full(card, live_copies)

    await state_dispenser.set(message.peer_id, AdminCardState.EDIT_VALUE, card_id=card_id)
    await message.answer(f"{text}\n\n{EDIT_HINT}", keyboard=cancel())


@labeler.message(state=AdminCardState.EDIT_VALUE)
async def do_edit(message: Message, **_: object) -> None:
    card_id = message.state_peer.payload["card_id"]
    field_text, sep, value_text = message.text.partition("=")
    if not sep:
        await message.answer("Формат: поле = значение", keyboard=cancel())
        return

    field_key = field_text.strip().lower()
    value_text = value_text.strip()

    async with get_session() as session:
        try:
            if field_key not in EDIT_FIELDS:
                raise ValidationError(f"Неизвестное поле. Доступны: {', '.join(EDIT_FIELDS)}.")

            field = EDIT_FIELDS[field_key]
            value: object = value_text
            if field == "rarity":
                value = parse_rarity(value_text)
            elif field == "transform_limit":
                value = parse_optional_limit(value_text)
            elif field == "number":
                value = parse_optional_slot_number(value_text)

            card = await card_service.update_card(session, card_id, **{field: value})
            live_copies = await cards_crud.count_owners(session, card.id)
            text = formatters.card_full(card, live_copies)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(
        f"Обновлено.\n\n{text}",
        keyboard=card_registry_detail_menu(
            card.id, 0, card_type=card.card_type, is_admin=True
        ),
    )


@labeler.message(payload={"cmd": "admin_card_delete"})
async def start_delete(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCardState.DELETE_PICK)
    await message.answer("Какую карту удаляем? Название или номер слота.", keyboard=cancel())


@labeler.message(payload_contains={"cmd": "admin_card_delete_select"})
async def select_delete_target(message: Message, **_: object) -> None:
    try:
        card_id = _payload_id(message)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin_cards())
        return
    await _show_delete_confirmation(message, card_id)


@labeler.message(state=AdminCardState.DELETE_PICK)
async def pick_delete_target(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            card = await card_service.find_card(session, message.text)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

        live_copies = await cards_crud.count_owners(session, card.id)
        card_id, name = card.id, card.name

    await clear_state(message.peer_id)
    warning = (
        f"\n\n⚠️ Живых копий карты: {live_copies} — свободные владения тоже удалятся."
        if live_copies
        else ""
    )
    await message.answer(
        f"Удалить карту «{name}»?{warning}",
        keyboard=confirm_menu(
            "admin_card_delete",
            card_id,
            cancel_payload={
                "cmd": "card_registry_view",
                "id": card_id,
                "page": 0,
                "type": card.card_type.name,
            },
        ),
    )


@labeler.message(payload_contains={"cmd": "admin_card_delete_confirm"})
async def confirm_delete(message: Message, **_: object) -> None:
    card_id = (message.get_payload_json() or {}).get("id")

    async with get_session() as session:
        try:
            name = await card_service.delete_card(session, int(card_id))
        except ServiceError as error:
            await message.answer(str(error), keyboard=back_to_admin_cards())
            return

    await message.answer(
        f"Карта «{name}» удалена из реестра.", keyboard=back_to_admin_cards()
    )


async def _open_card_editor(message: Message, card_id: int) -> None:
    async with get_session() as session:
        card = await cards_crud.get_by_id(session, card_id)
        if card is None:
            await message.answer("Карта не найдена.", keyboard=back_to_admin_cards())
            return
        live_copies = await cards_crud.count_owners(session, card.id)
        text = formatters.card_full(card, live_copies)

    await state_dispenser.set(
        message.peer_id, AdminCardState.EDIT_VALUE, card_id=card_id
    )
    await message.answer(f"{text}\n\n{EDIT_HINT}", keyboard=cancel())


async def _show_delete_confirmation(message: Message, card_id: int) -> None:
    async with get_session() as session:
        card = await cards_crud.get_by_id(session, card_id)
        if card is None:
            await message.answer("Карта не найдена.", keyboard=back_to_admin_cards())
            return
        live_copies = await cards_crud.count_owners(session, card.id)
        name = card.name

    await clear_state(message.peer_id)
    warning = (
        f"\n\n⚠️ Живых копий карты: {live_copies} — свободные владения тоже удалятся."
        if live_copies
        else ""
    )
    await message.answer(
        f"Точно удалить карту «{name}»? Отменить это действие будет нельзя.{warning}",
        keyboard=confirm_menu(
            "admin_card_delete",
            card_id,
            cancel_payload={
                "cmd": "card_registry_view",
                "id": card_id,
                "page": 0,
                "type": card.card_type.name,
            },
        ),
    )


def _payload_id(message: Message) -> int:
    value = (message.get_payload_json() or {}).get("id")
    try:
        card_id = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Некорректный ID карты.") from None
    if card_id <= 0:
        raise ValidationError("Некорректный ID карты.")
    return card_id
