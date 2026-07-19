import pytest

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import trophies as trophies_crud
from bot.database.models import CardType, Rarity, TrophyRank
from bot.services import book_slot_service, card_service, contour_service, trophy_service
from bot.services.errors import PermissionDenied, ValidationError
from bot.handlers.chat.trophies import _resolve_mentioned_character


@pytest.mark.asyncio
async def test_special_first_copy_uses_special_slot_and_extras_use_free_slots(session):
    character = await characters_crud.create(session, vk_id=1, name="Слава")
    special = await card_service.create_card(
        session,
        name="Ключ",
        card_type=CardType.SPECIAL,
        kind=CardType.SPECIAL.value,
        rarity=Rarity.H,
        number=7,
        admin_vk_id=99,
    )
    await card_service.grant_card_copies(session, special.id, character.id, quantity=3)

    usage = await book_slot_service.get_usage(session, character.id)

    assert usage.special_used == 1
    assert usage.free_used == 2
    assert usage.free_limit == 10


@pytest.mark.asyncio
async def test_free_slot_limit_blocks_new_copies(session):
    character = await characters_crud.create(session, vk_id=1, name="Слава")
    await card_service.grant_ordinary_cards(
        session,
        character_id=character.id,
        name="Верёвка",
        kind="Предмет",
        rarity=Rarity.H,
        quantity=10,
    )

    with pytest.raises(ValidationError, match="Свободные слоты заполнены"):
        await card_service.grant_ordinary_cards(
            session,
            character_id=character.id,
            name="Фонарь",
            kind="Предмет",
            rarity=Rarity.H,
            quantity=1,
        )


@pytest.mark.asyncio
async def test_admin_can_expand_free_slots_but_player_cannot(session, monkeypatch):
    character = await characters_crud.create(session, vk_id=1, name="Слава")
    monkeypatch.setattr("bot.services.auth_service.get_settings", lambda: type("S", (), {"is_admin": lambda self, value: value == 99})())

    updated = await book_slot_service.set_free_slot_limit(
        session, character_id=character.id, value=14, admin_vk_id=99
    )
    assert updated.free_slot_limit == 14
    with pytest.raises(PermissionDenied):
        await book_slot_service.set_free_slot_limit(
            session, character_id=character.id, value=15, admin_vk_id=1
        )


@pytest.mark.asyncio
async def test_contour_disassembly_requires_room_for_returning_cards(session, monkeypatch):
    character = await characters_crud.create(session, vk_id=1, name="Слава")
    contour_card = await card_service.create_card(
        session,
        name="Основа",
        card_type=CardType.CONTOUR,
        kind="Форма — Покров",
        rarity=Rarity.H,
        admin_vk_id=99,
    )
    contour_copy = await card_service.grant_card(
        session, contour_card.id, character.id
    )
    ordinary = await card_service.grant_ordinary_cards(
        session,
        character_id=character.id,
        name="Нить",
        kind="Предмет",
        rarity=Rarity.H,
        quantity=9,
    )
    monkeypatch.setattr("bot.services.auth_service.get_settings", lambda: type("S", (), {"is_admin": lambda self, value: value == 99})())
    contour = await contour_service.create_contour(
        session,
        character_id=character.id,
        ownership_ids=[contour_copy.id, ordinary[0].id],
        name="Узел",
        admin_vk_id=99,
    )
    await card_service.grant_ordinary_cards(
        session,
        character_id=character.id,
        name="Камень",
        kind="Предмет",
        rarity=Rarity.H,
        quantity=2,
    )

    with pytest.raises(ValidationError, match="Свободные слоты заполнены"):
        await contour_service.disassemble(
            session, contour_id=contour.id, admin_vk_id=99
        )


@pytest.mark.asyncio
async def test_trophy_is_immediate_permanent_award_without_progress(session, monkeypatch):
    character = await characters_crud.create(session, vk_id=1, name="Слава")
    monkeypatch.setattr("bot.services.auth_service.get_settings", lambda: type("S", (), {"is_admin": lambda self, value: value == 99})())

    trophy = await trophy_service.award(
        session,
        character_id=character.id,
        name="Первый шаг",
        rank="Бронзовый",
        description="Пережил первый выход.",
        reward="Памятный знак",
        admin_vk_id=99,
    )
    stored = await trophies_crud.list_for_character(session, character.id)

    assert trophy.rank is TrophyRank.BRONZE
    assert stored == [trophy]
    assert not hasattr(trophy, "progress")
    with pytest.raises(PermissionDenied):
        await trophy_service.award(
            session,
            character_id=character.id,
            name="Подделка",
            rank="Золотой",
            description="",
            reward="",
            admin_vk_id=1,
        )


@pytest.mark.asyncio
async def test_mention_resolves_one_character_and_requires_db_id_for_several(session):
    first = await characters_crud.create(session, vk_id=123, name="Слава")
    assert (
        await _resolve_mentioned_character(session, 123, "[id123|Слава]")
    ).id == first.id

    second = await characters_crud.create(session, vk_id=123, name="Свят")
    with pytest.raises(ValidationError, match="несколько анкет"):
        await _resolve_mentioned_character(session, 123, "[id123|Слава]")
    selected = await _resolve_mentioned_character(
        session, 123, f"[id123|Слава] #{second.id}"
    )
    assert selected.id == second.id
