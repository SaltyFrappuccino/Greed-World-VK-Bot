from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from bot.handlers.dm.admin import assistant
from bot.services.errors import ValidationError
from bot.states import AdminAssistantState, clear_state, state_dispenser


class _Message:
    def __init__(self, peer_id: int, session_id: int) -> None:
        self.peer_id = peer_id
        self.from_id = 500
        self.state_peer = SimpleNamespace(payload={"session_id": session_id})
        self.answers: list[tuple[str, str]] = []

    def get_payload_json(self) -> dict[str, int]:
        return {"plan_id": 7}

    async def answer(self, text: str, *, keyboard: str) -> None:
        self.answers.append((text, keyboard))


class _UsersAPI:
    async def get(self, *, user_ids):
        assert user_ids == ["idi_nahuy_dayn_tupoi"]
        return [SimpleNamespace(id=485208149)]


class _VKAPI:
    users = _UsersAPI()


@pytest.mark.asyncio
async def test_failed_confirmation_returns_to_same_ai_session(monkeypatch):
    message = _Message(peer_id=95001, session_id=42)

    @asynccontextmanager
    async def fake_session():
        yield object()

    async def fail_confirm(*_args, **_kwargs):
        raise ValidationError("Некорректный план")

    async def mark_failed(*_args, **_kwargs):
        return SimpleNamespace(session_id=42)

    monkeypatch.setattr(assistant, "get_session", fake_session)
    monkeypatch.setattr(assistant.assistant_service, "confirm_plan", fail_confirm)
    monkeypatch.setattr(assistant.assistant_service, "mark_plan_failed", mark_failed)

    try:
        await assistant._confirm(message, destructive=False)
        state = await state_dispenser.get(message.peer_id)

        assert state is not None
        assert state.state == AdminAssistantState.CHAT
        assert state.payload["session_id"] == 42
        assert "остались в AI-Ассистенте" in message.answers[-1][0]
        assert "admin_ai_assistant_new" in message.answers[-1][1]
    finally:
        await clear_state(message.peer_id)


@pytest.mark.asyncio
async def test_ai_handler_resolves_short_vk_url_to_stable_numeric_id():
    message = SimpleNamespace(
        text="Создай анкету для https://vk.ru/idi_nahuy_dayn_tupoi",
        ctx_api=_VKAPI(),
    )

    context = await assistant._resolved_vk_context(message)

    assert "https://vk.ru/idi_nahuy_dayn_tupoi" in context
    assert "числовой VK ID 485208149" in context
