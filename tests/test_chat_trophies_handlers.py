import asyncio
import types

import pytest

from bot.handlers.chat import trophies as trophies_mod


class DummyMessage:
    def __init__(self, from_id=99):
        self.from_id = from_id
        self._answers = []

    async def answer(self, text, **_):
        self._answers.append(text)


class DummyTrophy:
    def __init__(self, id=1, name="T", rank=None, description="d", reward="r"):
        self.id = id
        self.name = name
        self.rank = types.SimpleNamespace(name=(rank or "BRONZE"), value=(rank or "Бронзовый"))
        self.description = description
        self.reward = reward


class DummyCharacter:
    def __init__(self, id=1, name="Char"):
        self.id = id
        self.name = name


@pytest.mark.asyncio
async def test_award_parsing_handles_vk_mention_with_pipe(monkeypatch):
    # Arrange
    msg = DummyMessage(from_id=99)
    args = "[id485208149|@idi_nahuy_dayn_tupoi] | Бронзовый | Тест | Тест | -"

    async def fake_resolve(session, vk_id, query):
        return DummyCharacter(id=42, name="Player")

    async def fake_award(session, *, character_id, name, rank, description, reward, admin_vk_id):
        assert character_id == 42
        assert name == "Тест"
        assert rank.casefold() if isinstance(rank, str) else True
        return DummyTrophy(id=7, name=name)

    class FakeCtx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(trophies_mod, "_resolve_mentioned_character", fake_resolve)
    monkeypatch.setattr(trophies_mod.trophy_service, "award", fake_award)
    monkeypatch.setattr(trophies_mod, "get_session", lambda: FakeCtx())

    # Act
    await trophies_mod.award_trophy(msg, args)

    # Assert
    assert msg._answers
    assert "Трофей выдан персонажу" in msg._answers[-1]


@pytest.mark.asyncio
async def test_award_parsing_accepts_three_part_variant(monkeypatch):
    msg = DummyMessage(from_id=99)
    args = "[id123|Name] | Бронзовый | Тест | -"

    async def fake_resolve(session, vk_id, query):
        return DummyCharacter(id=5, name="A")

    async def fake_award(session, *, character_id, name, rank, description, reward, admin_vk_id):
        assert character_id == 5
        assert name == "Тест"
        # description should default to empty when '-' passed in 3-part variant
        return DummyTrophy(id=8, name=name)

    class FakeCtx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(trophies_mod, "_resolve_mentioned_character", fake_resolve)
    monkeypatch.setattr(trophies_mod.trophy_service, "award", fake_award)
    monkeypatch.setattr(trophies_mod, "get_session", lambda: FakeCtx())

    await trophies_mod.award_trophy(msg, args)
    assert msg._answers and "Трофей выдан персонажу" in msg._answers[-1]


@pytest.mark.asyncio
async def test_delete_trophy_by_mention_and_index(monkeypatch):
    msg = DummyMessage(from_id=99)
    args = "[id123|Name] 2"

    async def fake_resolve(session, vk_id, query):
        return DummyCharacter(id=10, name="X")

    async def fake_remove(session, *, trophy_id, admin_vk_id):
        # Return deleted trophy object
        return DummyTrophy(id=trophy_id, name="Deleted")

    async def fake_list_for_character(session, character_id):
        return [DummyTrophy(id=1, name="A"), DummyTrophy(id=2, name="B")]

    class FakeCtx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(trophies_mod, "_resolve_mentioned_character", fake_resolve)
    monkeypatch.setattr(trophies_mod.trophy_service, "remove", fake_remove)
    monkeypatch.setattr(trophies_mod.trophies_crud, "list_for_character", fake_list_for_character)
    monkeypatch.setattr(trophies_mod, "get_session", lambda: FakeCtx())

    await trophies_mod.delete_trophy(msg, args)
    assert msg._answers
    assert "Трофей удалён" in msg._answers[-1]
    assert "Deleted" in msg._answers[-1]


@pytest.mark.asyncio
async def test_delete_trophy_by_db_id_target(monkeypatch):
    msg = DummyMessage(from_id=99)
    args = "#45 1"

    async def fake_find_character(session, query):
        return DummyCharacter(id=45, name="Z")

    async def fake_remove(session, *, trophy_id, admin_vk_id):
        return DummyTrophy(id=trophy_id, name="Gone")

    async def fake_list_for_character(session, character_id):
        return [DummyTrophy(id=100, name="Only")]

    class FakeCtx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(trophies_mod.character_service, "find_character", fake_find_character)
    monkeypatch.setattr(trophies_mod.trophy_service, "remove", fake_remove)
    monkeypatch.setattr(trophies_mod.trophies_crud, "list_for_character", fake_list_for_character)
    monkeypatch.setattr(trophies_mod, "get_session", lambda: FakeCtx())

    await trophies_mod.delete_trophy(msg, args)
    assert msg._answers
    assert "Трофей удалён" in msg._answers[-1]
    assert "Gone" in msg._answers[-1]


@pytest.mark.asyncio
async def test_show_for_vk_does_not_include_delete_hint(monkeypatch):
    msg = DummyMessage(from_id=50)

    async def fake_resolve(session, vk_id, query):
        return DummyCharacter(id=77, name="NoHint")

    async def fake_list_for_character(session, character_id):
        return [DummyTrophy(id=3, name="One", rank="BRONZE")]

    class FakeCtx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(trophies_mod, "_resolve_mentioned_character", fake_resolve)
    monkeypatch.setattr(trophies_mod.trophies_crud, "list_for_character", fake_list_for_character)
    monkeypatch.setattr(trophies_mod, "get_session", lambda: FakeCtx())

    await trophies_mod._show_for_vk(msg, 77)
    assert msg._answers
    out = msg._answers[-1]
    assert "удалитьтрофей" not in out

