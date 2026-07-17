from vkbottle import BaseStateGroup, BuiltinStateDispenser

#: Общий диспенсер: создаётся здесь, чтобы и хендлеры, и Bot работали с одним состоянием.
state_dispenser = BuiltinStateDispenser()


class ProfileState(BaseStateGroup):
    EDIT_VALUE = "edit_value"


class CardsState(BaseStateGroup):
    SEARCH = "search"


class TransferState(BaseStateGroup):
    RECIPIENT = "recipient"
    AMOUNT = "amount"


class AdminCardState(BaseStateGroup):
    TYPE = "type"
    ADD = "add"
    EDIT_PICK = "edit_pick"
    EDIT_VALUE = "edit_value"
    DELETE_PICK = "delete_pick"


class AdminShakeiState(BaseStateGroup):
    GRANT = "grant"
    DEDUCT = "deduct"


class AdminStatsState(BaseStateGroup):
    INPUT = "input"


class AdminCharacterState(BaseStateGroup):
    OWNER = "owner"
    TEMPLATE = "template"


class AdminAIState(BaseStateGroup):
    CHARACTER_OWNER = "character_owner"
    CHARACTER_SOURCE = "character_source"
    CHARACTER_CONFIRM = "character_confirm"
    CONTOUR_CHARACTER = "contour_character"
    CONTOUR_SOURCE = "contour_source"
    CONTOUR_CONFIRM = "contour_confirm"


async def clear_state(peer_id: int) -> None:
    """Сброс состояния. Встроенный delete() кидает KeyError на пустом peer_id."""
    if await state_dispenser.get(peer_id) is not None:
        await state_dispenser.delete(peer_id)
