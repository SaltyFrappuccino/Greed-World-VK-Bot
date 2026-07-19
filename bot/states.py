from vkbottle import BaseStateGroup, BuiltinStateDispenser

RETURN_CONTEXT_KEY = "__return_context__"


class NavigationStateDispenser(BuiltinStateDispenser):
    """Сохраняет экран, к которому должна вернуть отмена текущего сценария."""

    async def set(self, peer_id: int, state: str, **payload: object) -> None:
        if RETURN_CONTEXT_KEY not in payload:
            current = await self.get(peer_id)
            current_payload = current.payload if current is not None else {}
            context = current_payload.get(RETURN_CONTEXT_KEY)
            if not isinstance(context, dict):
                context = default_return_context(state, payload)
            payload[RETURN_CONTEXT_KEY] = context
        await super().set(peer_id, state, **payload)


#: Общий диспенсер: создаётся здесь, чтобы и хендлеры, и Bot работали с одним состоянием.
state_dispenser = NavigationStateDispenser()


class CardsState(BaseStateGroup):
    SEARCH = "search"


class TransferState(BaseStateGroup):
    RECIPIENT = "recipient"
    AMOUNT = "amount"


class AdminCardState(BaseStateGroup):
    TYPE = "type"
    ADD_MODE = "add_mode"
    ORDINARY_CHARACTER = "ordinary_character"
    ORDINARY_QUANTITY = "ordinary_quantity"
    ADD_TEMPLATE = "add_template"
    ADD_AI_SOURCE = "add_ai_source"
    ADD_AI_CONFIRM = "add_ai_confirm"
    ADD_NAME = "add_name"
    ADD_KIND = "add_kind"
    ADD_CONTOUR_SUBTYPE = "add_contour_subtype"
    ADD_RARITY = "add_rarity"
    ADD_NUMBER = "add_number"
    ADD_LIMIT = "add_limit"
    ADD_DESCRIPTION = "add_description"
    ADD_USAGE = "add_usage"
    ADD_SPELL_ACTIVATION = "add_spell_activation"
    ADD_SPELL_CONSUMPTION = "add_spell_consumption"
    EDIT_PICK = "edit_pick"
    EDIT_VALUE = "edit_value"
    DELETE_PICK = "delete_pick"
    GRANT_CHARACTER = "grant_character"
    CHARACTER_GRANT_CARD = "character_grant_card"
    CHARACTER_REVOKE_CARD = "character_revoke_card"
    CHARACTER_GRANT_SPECIAL = "character_grant_special"
    CHARACTER_GRANT_REGISTRY = "character_grant_registry"
    CHARACTER_REVOKE_SPECIAL = "character_revoke_special"
    CHARACTER_REVOKE_REGISTRY = "character_revoke_registry"
    CHARACTER_ADD_ORDINARY = "character_add_ordinary"
    CHARACTER_REVOKE_ORDINARY = "character_revoke_ordinary"


class AdminShakeiState(BaseStateGroup):
    AMOUNT = "amount"


class AdminStatsState(BaseStateGroup):
    INPUT = "input"


class AdminTrophyState(BaseStateGroup):
    AWARD = "award"


class AdminBookState(BaseStateGroup):
    FREE_SLOT_LIMIT = "free_slot_limit"


class AdminCharacterState(BaseStateGroup):
    OWNER = "owner"
    TEMPLATE = "template"
    EDIT_PICK = "edit_pick"
    EDIT_VALUE = "edit_value"


class AdminArtState(BaseStateGroup):
    UPLOAD = "upload"
    CAPTION = "caption"


class AdminAIState(BaseStateGroup):
    CHARACTER_OWNER = "character_owner"
    CHARACTER_SOURCE = "character_source"
    CHARACTER_CONFIRM = "character_confirm"
    CONTOUR_CHARACTER = "contour_character"
    CONTOUR_SOURCE = "contour_source"
    CONTOUR_CONFIRM = "contour_confirm"


class AdminAssistantState(BaseStateGroup):
    CHAT = "admin_assistant_chat"
    PLAN_CONFIRM = "admin_assistant_plan_confirm"
    DESTRUCTIVE_CONFIRM = "admin_assistant_destructive_confirm"
    EXECUTING = "admin_assistant_executing"


class AdminContourState(BaseStateGroup):
    CREATE_COMPONENTS = "create_components"
    CREATE_MODE = "create_mode"
    CREATE_MANUAL = "create_manual"
    CREATE_TEMPLATE = "create_template"
    CAPACITY_VALUE = "capacity_value"
    LIMIT_VALUE = "limit_value"
    EDIT_VALUE = "edit_value"
    ADD_COMPONENT = "add_component"
    REPLACE_COMPONENT = "replace_component"
    AI_SOURCE = "ai_source"
    AI_CONFIRM = "ai_confirm"


async def clear_state(peer_id: int) -> None:
    """Сброс состояния. Встроенный delete() кидает KeyError на пустом peer_id."""
    if await state_dispenser.get(peer_id) is not None:
        await state_dispenser.delete(peer_id)


def return_context(payload: dict[str, object] | None) -> dict[str, object]:
    if payload is None:
        return {"screen": "main"}
    context = payload.get(RETURN_CONTEXT_KEY)
    return context if isinstance(context, dict) else {"screen": "main"}


def default_return_context(
    state: str, payload: dict[str, object]
) -> dict[str, object]:
    state_name = str(state)
    character_id = _positive_id(payload.get("character_id"))
    card_id = _positive_id(payload.get("card_id"))
    contour_id = _positive_id(payload.get("contour_id"))

    if state_name.startswith("CardsState"):
        return {"screen": "cards"}
    if state_name.startswith("TransferState"):
        return {"screen": "main"}
    if state_name.startswith("AdminShakeiState") and character_id:
        return {"screen": "character_shakei", "id": character_id}
    if state_name.startswith("AdminCardState"):
        if state_name == AdminCardState.GRANT_CHARACTER and card_id:
            return {"screen": "card_owners", "id": card_id}
        if character_id:
            return {"screen": "character_cards", "id": character_id}
        if card_id:
            return {"screen": "card", "id": card_id}
        return {"screen": "admin_cards"}
    if state_name.startswith("AdminCharacterState"):
        if character_id:
            return {"screen": "character", "id": character_id}
        return {"screen": "admin_characters"}
    if state_name.startswith("AdminArtState"):
        if character_id:
            return {"screen": "character_arts", "id": character_id}
        return {"screen": "admin_characters"}
    if state_name.startswith("AdminStatsState"):
        return {"screen": "admin_characters"}
    if state_name.startswith("AdminTrophyState") and character_id:
        return {"screen": "character_trophies", "id": character_id}
    if state_name.startswith("AdminBookState") and character_id:
        return {"screen": "character", "id": character_id}
    if state_name.startswith("AdminContourState"):
        if state_name == AdminContourState.LIMIT_VALUE and character_id:
            return {"screen": "character", "id": character_id}
        if state_name.startswith(f"{AdminContourState.__name__}:create") and character_id:
            return {"screen": "character_contours", "id": character_id}
        if contour_id:
            return {"screen": "contour", "id": contour_id}
        if character_id:
            return {"screen": "character_contours", "id": character_id}
        return {"screen": "admin_characters"}
    if state_name.startswith("AdminAIState"):
        if contour_id:
            return {"screen": "contour", "id": contour_id}
        if character_id:
            return {"screen": "character_contours", "id": character_id}
        return {"screen": "admin_characters"}
    if state_name.startswith("Admin"):
        return {"screen": "admin"}
    return {"screen": "main"}


def _positive_id(value: object) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
