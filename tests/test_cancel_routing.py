import json

import pytest
from unittest.mock import AsyncMock

from bot.handlers.dm import menu
from bot.handlers.dm.menu import cancel
from bot.states import (
    AdminCardState,
    AdminCharacterState,
    AdminContourState,
    RETURN_CONTEXT_KEY,
    state_dispenser,
)


class _Message:
    peer_id = 987654321

    def __init__(self):
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


@pytest.mark.asyncio
async def test_cancel_from_card_state_returns_cards_section():
    message = _Message()
    await state_dispenser.set(message.peer_id, AdminCardState.TYPE)

    await cancel(message, is_admin=True)

    text, kwargs = message.answers[-1]
    keyboard = json.loads(kwargs["keyboard"])
    labels = [button["action"]["label"] for row in keyboard["buttons"] for button in row]
    assert "карты" in text.lower()
    assert "Добавить карту" in labels
    assert await state_dispenser.get(message.peer_id) is None


@pytest.mark.asyncio
async def test_cancel_from_character_card_grant_returns_same_character(monkeypatch):
    message = _Message()
    render = AsyncMock()
    monkeypatch.setattr(menu, "render_return", render)
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.CHARACTER_GRANT_SPECIAL,
        character_id=42,
    )

    await cancel(message, is_admin=True)

    render.assert_awaited_once_with(
        message,
        {"screen": "character_cards", "id": 42},
        is_admin=True,
    )
    assert await state_dispenser.get(message.peer_id) is None


@pytest.mark.asyncio
async def test_return_context_survives_all_steps_of_a_scenario():
    peer_id = 987654322
    await state_dispenser.set(
        peer_id,
        AdminContourState.CREATE_COMPONENTS,
        character_id=7,
        slot=1,
    )
    await state_dispenser.set(
        peer_id,
        AdminContourState.CREATE_MODE,
        character_id=7,
        slot=1,
    )

    state = await state_dispenser.get(peer_id)

    assert state.payload[RETURN_CONTEXT_KEY] == {
        "screen": "character_contours",
        "id": 7,
    }
    await state_dispenser.delete(peer_id)


@pytest.mark.asyncio
async def test_cancel_from_character_state_returns_characters_section():
    message = _Message()
    await state_dispenser.set(message.peer_id, AdminCharacterState.OWNER)

    await cancel(message, is_admin=True)

    text, kwargs = message.answers[-1]
    keyboard = json.loads(kwargs["keyboard"])
    labels = [
        button["action"]["label"]
        for row in keyboard["buttons"]
        for button in row
    ]
    assert "анкеты" in text.lower()
    assert "Добавить анкету" in labels
    assert await state_dispenser.get(message.peer_id) is None
