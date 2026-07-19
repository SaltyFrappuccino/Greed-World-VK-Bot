from contextlib import asynccontextmanager

import pytest

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import CardType, Rarity
from bot.handlers.dm.admin import commands
from bot.services import card_service
from bot.utils import formatters


class _Message:
    peer_id = 7654321
    from_id = 99

    def __init__(self):
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


def _use_session(monkeypatch, session):
    @asynccontextmanager
    async def fake_get_session():
        yield session

    monkeypatch.setattr(commands, "get_session", fake_get_session)


@pytest.mark.asyncio
async def test_admin_can_grant_and_revoke_card_by_public_ids(
    session, monkeypatch
):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    card = await card_service.create_card(
        session,
        name="Ясень",
        card_type=CardType.SPECIAL,
        kind=CardType.SPECIAL.value,
        rarity=Rarity.S,
        admin_vk_id=99,
        number=17,
        transform_limit=2,
    )
    _use_session(monkeypatch, session)
    message = _Message()

    await commands.grant_card(message, str(character.id), str(card.number))

    assert (
        await cards_crud.get_ownership(session, card.id, character.id)
        is not None
    )
    assert f"#{character.id}" in message.answers[-1][0]
    assert f"#{card.id}" in message.answers[-1][0]

    await commands.revoke_card(message, str(character.id), str(card.number))

    assert await cards_crud.get_ownership(session, card.id, character.id) is None


@pytest.mark.asyncio
async def test_admin_can_change_shakei_with_signed_delta(session, monkeypatch):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    _use_session(monkeypatch, session)
    message = _Message()

    await commands.change_shakei(message, str(character.id), "+100")
    assert character.shakei_balance == 100
    assert "+100" in message.answers[-1][0]

    await commands.change_shakei(message, str(character.id), "-40")
    assert character.shakei_balance == 60
    assert "-40" in message.answers[-1][0]


@pytest.mark.asyncio
async def test_profile_and_card_formatters_show_database_ids(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    card = await card_service.create_card(
        session,
        name="Верёвка",
        card_type=CardType.SPELL,
        kind=CardType.SPELL.value,
        rarity=Rarity.H,
        admin_vk_id=99,
    )

    profile = formatters.character_profile(character, [card], [])

    assert f"ID анкеты в БД: #{character.id}" in profile
    assert f"#{card.registry_number} · {card.name}" in profile
    assert f"Внутренний ID БД: #{card.id}" in formatters.card_short(card)
    assert f"Внутренний ID БД: #{card.id}" in formatters.card_full(card)


def test_admin_id_commands_are_loaded_before_state_handlers(monkeypatch):
    monkeypatch.setenv("VK_COMMUNITY_TOKEN", "test")
    monkeypatch.setenv("VK_GROUP_ID", "1")

    from bot.config import get_settings
    from bot.main import create_bot

    get_settings.cache_clear()
    handlers = create_bot().labeler.message_view.handlers
    command_indexes = [
        index
        for index, handler in enumerate(handlers)
        if handler.handler.__module__ == commands.__name__
    ]
    admin_state_indexes = [
        index
        for index, handler in enumerate(handlers)
        if ".handlers.dm.admin." in handler.handler.__module__
        and any(type(rule).__name__ == "StateRule" for rule in handler.rules)
    ]

    assert command_indexes
    assert admin_state_indexes
    assert max(command_indexes) < min(admin_state_indexes)
