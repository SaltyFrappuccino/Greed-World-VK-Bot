import json
from types import SimpleNamespace

import pytest

from bot.config import get_settings
from bot.services import ai_service


class _FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.request = None

    async def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class _FakeClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


@pytest.mark.asyncio
async def test_character_generation_uses_strict_json_schema(monkeypatch):
    content = json.dumps(
        {
            "name": "Ава",
            "age": 30,
            "gender": "Женский",
            "appearance": "Высокая",
            "personality": "Спокойная",
            "biography": "Прибыла недавно",
            "stress_resistance": 5,
            "speech": 4,
            "intuition": 3,
            "spine": 2,
            "will": 5,
            "scent": 4,
            "skills": ["обучена переговорам"],
            "additional": "",
        },
        ensure_ascii=False,
    )
    completions = _FakeCompletions(content)
    monkeypatch.setenv("AITUNNEL_API_KEY", "test-key")
    monkeypatch.setattr(
        ai_service, "AsyncOpenAI", lambda **_: _FakeClient(completions)
    )
    get_settings.cache_clear()

    draft = await ai_service.generate_character(
        "Исходная анкета", image_urls=["https://example.com/appearance.jpg"]
    )

    assert draft.name == "Ава"
    assert completions.request["model"] == "gemini-3.1-flash-lite"
    response_format = completions.request["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["additionalProperties"] is False
    messages = completions.request["messages"]
    assert "Запрещено добавлять факты" in messages[0]["content"]
    assert messages[1]["content"][0] == {
        "type": "text",
        "text": "Исходная анкета",
    }
    assert messages[1]["content"][1]["image_url"]["url"].endswith(
        "appearance.jpg"
    )
    get_settings.cache_clear()


def test_character_fields_rejects_stats_missing_from_source():
    draft = ai_service.CharacterDraft(
        name="Ава",
        age=None,
        gender="",
        appearance="",
        personality="",
        biography="",
        stress_resistance=None,
        speech=None,
        intuition=None,
        spine=None,
        will=None,
        scent=None,
        skills=[],
        additional="",
    )

    with pytest.raises(ai_service.ValidationError, match="не указаны статы"):
        ai_service.character_fields(draft)
