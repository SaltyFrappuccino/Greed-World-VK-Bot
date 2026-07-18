from vkbottle import BaseStateGroup, BuiltinStateDispenser

#: Общий диспенсер: создаётся здесь, чтобы и хендлеры, и Bot работали с одним состоянием.
state_dispenser = BuiltinStateDispenser()


class CardsState(BaseStateGroup):
    SEARCH = "search"


class TransferState(BaseStateGroup):
    RECIPIENT = "recipient"
    AMOUNT = "amount"


class AdminCardState(BaseStateGroup):
    TYPE = "type"
    ADD_MODE = "add_mode"
    ADD_TEMPLATE = "add_template"
    ADD_NAME = "add_name"
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


class AdminShakeiState(BaseStateGroup):
    AMOUNT = "amount"


class AdminStatsState(BaseStateGroup):
    INPUT = "input"


class AdminCharacterState(BaseStateGroup):
    OWNER = "owner"
    TEMPLATE = "template"
    EDIT_PICK = "edit_pick"
    EDIT_VALUE = "edit_value"


class AdminAIState(BaseStateGroup):
    CHARACTER_OWNER = "character_owner"
    CHARACTER_SOURCE = "character_source"
    CHARACTER_CONFIRM = "character_confirm"
    CONTOUR_CHARACTER = "contour_character"
    CONTOUR_SOURCE = "contour_source"
    CONTOUR_CONFIRM = "contour_confirm"


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
