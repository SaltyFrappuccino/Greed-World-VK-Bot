import pytest

from bot.handlers.dm.admin import contours
from bot.states import AdminContourState, clear_state, state_dispenser


class _FakeMessage:
    def __init__(self, peer_id: int):
        self.peer_id = peer_id
        self.answers: list[str] = []

    async def answer(self, text: str, **_kwargs) -> None:
        self.answers.append(text)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state_name",
    [
        AdminContourState.CREATE_COMPONENTS,
        AdminContourState.CREATE_MODE,
        AdminContourState.ADD_COMPONENT,
        AdminContourState.REPLACE_COMPONENT,
        AdminContourState.AI_SOURCE,
        AdminContourState.AI_CONFIRM,
    ],
)
async def test_contour_router_accepts_fresh_vkbottle_state(state_name):
    peer_id = 92000 + list(AdminContourState).index(state_name)
    message = _FakeMessage(peer_id)
    try:
        await state_dispenser.set(peer_id, state_name, marker="fresh")

        state = await contours._require_state(message, state_name)

        assert state is not None
        assert state.payload["marker"] == "fresh"
        assert message.answers == []
    finally:
        await clear_state(peer_id)


@pytest.mark.asyncio
async def test_contour_router_rejects_genuinely_different_state():
    peer_id = 92999
    message = _FakeMessage(peer_id)
    try:
        await state_dispenser.set(peer_id, AdminContourState.CREATE_MODE)

        state = await contours._require_state(
            message, AdminContourState.CREATE_COMPONENTS
        )

        assert state is None
        assert message.answers == ["Сценарий устарел или был отменён."]
    finally:
        await clear_state(peer_id)
