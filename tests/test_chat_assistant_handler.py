from types import SimpleNamespace

import pytest

from bot.handlers.chat import assistant
from bot.services.admin_ai.runtime import AssistantAttachment


class _Message:
    ctx_api = object()
    peer_id = 123


@pytest.mark.asyncio
async def test_chat_assistant_uploads_document_with_vk_uploader(monkeypatch):
    calls = []

    class _Uploader:
        def __init__(self, api, attachment_name):
            calls.append((api, attachment_name))

        async def upload(self, data, **kwargs):
            calls.append((data, kwargs))
            return "doc-1_2"

    monkeypatch.setattr(assistant, "DocMessagesUploader", _Uploader)
    item = AssistantAttachment(filename="result.xlsx", data=b"xlsx")

    result = await assistant._upload_attachments(_Message(), [item])

    assert result == [("document", "doc-1_2", "result.xlsx")]
    assert calls[-1] == (
        b"xlsx",
        {"peer_id": 123, "title": "result.xlsx"},
    )


@pytest.mark.asyncio
async def test_confirmed_chat_plan_returns_to_chat_and_shows_result(monkeypatch):
    plan = SimpleNamespace(id=7, session_id=11)
    state_calls = []
    answers = []

    class _SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return False

    async def confirm_plan(*_args, **_kwargs):
        return plan, True

    async def set_state(peer_id, state, **payload):
        state_calls.append((peer_id, state, payload))

    async def fake_answer_long(message, text, **_kwargs):
        answers.append((message, text))

    monkeypatch.setattr(assistant, "get_session", lambda: _SessionContext())
    monkeypatch.setattr(assistant.assistant_service, "confirm_plan", confirm_plan)
    monkeypatch.setattr(
        assistant.assistant_service, "format_result", lambda _plan: "Готово"
    )
    monkeypatch.setattr(assistant.state_dispenser, "set", set_state)
    monkeypatch.setattr(assistant, "answer_long", fake_answer_long)
    message = _Message()
    message.from_id = 99

    await assistant._confirm_chat_plan(message, destructive=False, plan_id=7)

    assert state_calls[-1][2] == {"session_id": 11}
    assert answers[-1] == (message, "Готово")
