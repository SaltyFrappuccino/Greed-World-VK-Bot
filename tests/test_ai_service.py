import json
import logging
from types import SimpleNamespace

import pytest

from bot.config import get_settings
from bot.services import ai_service
from bot.services.admin_ai import llm as admin_ai_llm
from bot.services.content_ai import client as content_ai_client


class _FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.request = None

    async def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class _SequenceCompletions:
    def __init__(self, contents):
        self.contents = list(contents)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        content = self.contents.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class _FakeClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


@pytest.mark.asyncio
async def test_admin_assistant_uses_json_mode_without_native_tools(monkeypatch, caplog):
    content = json.dumps(
        {
            "kind": "read_tools",
            "message": "Найду анкету.",
            "tools": [{"name": "find_character", "arguments": {"query": "Ава"}}],
            "actions": [],
            "warnings": [],
        },
        ensure_ascii=False,
    )
    completions = _FakeCompletions(content)
    monkeypatch.setenv("DSLAB_API_KEY", "test-key")
    monkeypatch.setenv("DSLAB_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DSLAB_AGENT_MAX_TOKENS", "8000")
    monkeypatch.setattr(
        admin_ai_llm, "AsyncOpenAI", lambda **_: _FakeClient(completions)
    )
    get_settings.cache_clear()

    caplog.set_level(logging.INFO, logger="zhadny_mir.ai_agent.llm")
    turn = await ai_service.generate_admin_assistant_turn(
        [{"role": "user", "content": "Покажи Аву"}],
        request_id="test-request",
        round_number=1,
    )

    assert turn.kind == "read_tools"
    assert turn.tools[0].name == "find_character"
    assert "tools" not in completions.request
    assert completions.request["response_format"] == {"type": "json_object"}
    assert completions.request["max_tokens"] == 8000
    system_prompt = completions.request["messages"][0]["content"]
    assert "H, G, F, E, D, C, B, A, S, SS" in system_prompt
    assert "Уточняй минимально необходимое" in system_prompt
    assert "Тип карты определяет способ хранения" in system_prompt
    assert "Пример:" not in system_prompt
    assert "request.start request_id=test-request round=1" in caplog.text
    assert "request.done request_id=test-request round=1" in caplog.text
    assert "parse.ok request_id=test-request round=1 kind=read_tools" in caplog.text
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_assistant_repairs_invalid_model_json(monkeypatch):
    completions = _SequenceCompletions(
        [
            '{"kind":"answer","message":"Готово","tools":"сломано"}',
            '{"kind":"answer","message":"Готово","tools":[],"actions":[],"warnings":[]}',
        ]
    )
    monkeypatch.setenv("DSLAB_API_KEY", "test-key")
    monkeypatch.setenv("DSLAB_MODEL", "deepseek-v4-flash")
    monkeypatch.setattr(
        admin_ai_llm, "AsyncOpenAI", lambda **_: _FakeClient(completions)
    )
    get_settings.cache_clear()

    turn = await ai_service.generate_admin_assistant_turn(
        [{"role": "user", "content": "Ответь"}]
    )

    assert turn.kind == "answer"
    assert turn.message == "Готово"
    assert len(completions.requests) == 2
    assert completions.requests[1]["max_tokens"] == 1500
    get_settings.cache_clear()


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
    client_kwargs = {}

    def make_client(**kwargs):
        client_kwargs.update(kwargs)
        return _FakeClient(completions)

    monkeypatch.setenv("DSLAB_API_KEY", "test-key")
    monkeypatch.setenv("DSLAB_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DSLAB_VISION_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setattr(content_ai_client, "AsyncOpenAI", make_client)
    get_settings.cache_clear()

    draft = await ai_service.generate_character(
        "Исходная анкета", image_urls=["https://example.com/appearance.jpg"]
    )

    assert draft.name == "Ава"
    assert client_kwargs == {
        "api_key": "test-key",
        "base_url": "https://api.dslab.tech/v1",
    }
    assert completions.request["model"] == "gemini-2.5-flash-lite"
    assert completions.request["temperature"] == 0
    response_format = completions.request["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["additionalProperties"] is False
    messages = completions.request["messages"]
    assert "Запрещено добавлять факты" in messages[0]["content"]
    assert "<SOURCE>\nИсходная анкета\n</SOURCE>" in messages[1]["content"][0]["text"]
    assert messages[1]["content"][1]["image_url"]["url"].endswith(
        "appearance.jpg"
    )
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_text_character_generation_uses_deepseek(monkeypatch):
    content = json.dumps(
        {
            "name": "",
            "age": 30,
            "gender": "Женский",
            "appearance": "",
            "personality": "",
            "biography": "",
            "stress_resistance": 5,
            "speech": 4,
            "intuition": 3,
            "spine": 2,
            "will": 5,
            "scent": 4,
            "skills": [],
            "additional": "",
        },
        ensure_ascii=False,
    )
    completions = _FakeCompletions(content)
    monkeypatch.setenv("DSLAB_API_KEY", "test-key")
    monkeypatch.setenv("DSLAB_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DSLAB_VISION_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setattr(
        content_ai_client, "AsyncOpenAI", lambda **_: _FakeClient(completions)
    )
    get_settings.cache_clear()

    draft = await ai_service.generate_character("Имя персонажа: Ава")

    assert draft.name == "Ава"
    assert completions.request["model"] == "deepseek-v4-flash"
    assert isinstance(completions.request["messages"][1]["content"], str)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_character_generation_restores_omitted_labeled_section(monkeypatch):
    base = {
        "name": "Ава",
        "age": 30,
        "gender": "Женский",
        "appearance": "",
        "personality": "Спокойная",
        "biography": "",
        "stress_resistance": 5,
        "speech": 4,
        "intuition": 3,
        "spine": 2,
        "will": 5,
        "scent": 4,
        "skills": [],
        "additional": "",
    }
    completions = _SequenceCompletions([json.dumps(base, ensure_ascii=False)])
    monkeypatch.setenv("DSLAB_API_KEY", "test-key")
    monkeypatch.setenv("DSLAB_MODEL", "deepseek-v4-flash")
    monkeypatch.setattr(
        content_ai_client, "AsyncOpenAI", lambda **_: _FakeClient(completions)
    )
    get_settings.cache_clear()

    draft = await ai_service.generate_character(
        """➤ Внешность
（Как персонаж выглядел дома и как выглядит сейчас.）
Высокая, носит белый плащ.

✎ Характер
Спокойная"""
    )

    assert draft.appearance == "Высокая, носит белый плащ."
    assert len(completions.requests) == 1
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_character_generation_retries_missing_image_description(monkeypatch):
    base = {
        "name": "Ава",
        "age": 30,
        "gender": "Женский",
        "appearance": "",
        "personality": "",
        "biography": "",
        "stress_resistance": 5,
        "speech": 4,
        "intuition": 3,
        "spine": 2,
        "will": 5,
        "scent": 4,
        "skills": [],
        "additional": "",
    }
    repaired = {**base, "appearance": "Высокая, носит белый плащ."}
    completions = _SequenceCompletions(
        [json.dumps(base, ensure_ascii=False), json.dumps(repaired, ensure_ascii=False)]
    )
    monkeypatch.setenv("DSLAB_API_KEY", "test-key")
    monkeypatch.setenv("DSLAB_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DSLAB_VISION_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setattr(
        content_ai_client, "AsyncOpenAI", lambda **_: _FakeClient(completions)
    )
    get_settings.cache_clear()

    draft = await ai_service.generate_character(
        "Имя: Ава", image_urls=["https://example.com/appearance.jpg"]
    )

    assert draft.appearance == "Высокая, носит белый плащ."
    assert len(completions.requests) == 2
    assert "Внешность по изображению" in completions.requests[1]["messages"][1][
        "content"
    ][0]["text"]
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


@pytest.mark.asyncio
async def test_contour_ai_cannot_change_selected_cards(monkeypatch):
    content = json.dumps(
        {
            "name": "Грозовой покров",
            "appearance": "Искры вокруг тела",
            "primary_effect": "Покрывает тело электричеством",
            "additional_capabilities": "",
            "activation_conditions": "Назвать Контур",
            "duration": "Одна сцена",
            "conductivity": "1",
            "overload_impact": "Поднимает Перегрузку",
        },
        ensure_ascii=False,
    )
    completions = _FakeCompletions(content)
    monkeypatch.setenv("DSLAB_API_KEY", "test-key")
    monkeypatch.setattr(
        content_ai_client, "AsyncOpenAI", lambda **_: _FakeClient(completions)
    )
    get_settings.cache_clear()

    draft = await ai_service.generate_contour(
        "Сделай защитную способность",
        "Имя: Ава",
        "Карта #1: Покров\nКарта #2: Молния",
    )

    assert draft.name == "Грозовой покров"
    schema = completions.request["response_format"]["json_schema"]["schema"]
    assert "composition" not in schema["properties"]
    messages = completions.request["messages"]
    assert "Запрещено добавлять, заменять" in messages[0]["content"]
    assert "Карта #1: Покров" in messages[1]["content"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_card_ai_receives_selected_type_and_system_context(monkeypatch):
    content = json.dumps(
        {
            "name": "Грозовая печать",
            "kind": "Заклинание",
            "description": "Поражает отмеченную цель молнией.",
            "usage": "Команда активации: Гроза. Расходуется после применения.",
            "rarity": "H",
        },
        ensure_ascii=False,
    )
    completions = _FakeCompletions(content)
    monkeypatch.setenv("DSLAB_API_KEY", "test-key")
    monkeypatch.setattr(
        content_ai_client, "AsyncOpenAI", lambda **_: _FakeClient(completions)
    )
    get_settings.cache_clear()

    draft = await ai_service.generate_card(
        "Молния по цели, после этого карта пропадает",
        ai_service.CardType.SPELL,
    )

    assert draft.name == "Грозовая печать"
    messages = completions.request["messages"]
    assert "Тип карты уже выбран администратором: Заклинание" in messages[0]["content"]
    assert "Не меняй его" in messages[0]["content"]
    assert "Молния по цели" in messages[1]["content"]
    get_settings.cache_clear()
