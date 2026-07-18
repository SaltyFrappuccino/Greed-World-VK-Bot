import json

import pytest

from bot.handlers.dm.menu import cancel
from bot.states import AdminCardState, AdminCharacterState, state_dispenser


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
