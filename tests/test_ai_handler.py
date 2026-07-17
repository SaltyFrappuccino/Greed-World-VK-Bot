from types import SimpleNamespace

import pytest

from bot.handlers.dm.admin import ai
from bot.states import AdminAIState, clear_state, state_dispenser


class _FakeMessage:
    def __init__(self, peer_id, text="", photos=None):
        self.peer_id = peer_id
        self.text = text
        self._photos = photos or []
        self.state_peer = None
        self.answers = []

    def get_photo_attachments(self):
        return self._photos

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


@pytest.mark.asyncio
async def test_require_state_accepts_vkbottle_state_representation():
    peer_id = 91001
    try:
        await state_dispenser.set(peer_id, AdminAIState.CHARACTER_CONFIRM)
        message = SimpleNamespace(peer_id=peer_id)

        state = await ai._require_state(message, AdminAIState.CHARACTER_CONFIRM)

        assert state.state == AdminAIState.CHARACTER_CONFIRM
    finally:
        await clear_state(peer_id)


@pytest.mark.asyncio
async def test_collect_source_accumulates_messages_and_largest_photo():
    peer_id = 91002
    small = SimpleNamespace(url="https://example.com/small.jpg", width=100, height=100)
    large = SimpleNamespace(url="https://example.com/large.jpg", width=1000, height=800)
    photo = SimpleNamespace(sizes=[small, large], photo_256=None)
    try:
        await state_dispenser.set(
            peer_id,
            AdminAIState.CHARACTER_SOURCE,
            owner_vk_id=1,
            source_parts=[],
            image_urls=[],
        )
        first = _FakeMessage(peer_id, "Первая часть")
        first.state_peer = await state_dispenser.get(peer_id)
        await ai._collect_source(
            first, AdminAIState.CHARACTER_SOURCE, "admin_ai_character"
        )

        second = _FakeMessage(peer_id, "Вторая часть", [photo])
        second.state_peer = await state_dispenser.get(peer_id)
        await ai._collect_source(
            second, AdminAIState.CHARACTER_SOURCE, "admin_ai_character"
        )

        state = await state_dispenser.get(peer_id)
        assert state.payload["source_parts"] == ["Первая часть", "Вторая часть"]
        assert state.payload["image_urls"] == ["https://example.com/large.jpg"]
    finally:
        await clear_state(peer_id)
