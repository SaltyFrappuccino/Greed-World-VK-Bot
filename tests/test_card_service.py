import pytest
from sqlalchemy import select

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import CardType, CardUsage, Rarity
from bot.services import card_service
from bot.services.errors import TransformLimitReached, ValidationError


@pytest.mark.asyncio
async def test_transform_limit_is_freed_after_revoke(session):
    first = await characters_crud.create(session, vk_id=1, name="Первый")
    second = await characters_crud.create(session, vk_id=2, name="Второй")
    card = await card_service.create_card(
        session,
        name="Ясень",
        card_type=CardType.SPECIAL,
        kind="Особая",
        rarity=Rarity.S,
        admin_vk_id=99,
        number=17,
        transform_limit=1,
    )

    await card_service.grant_card(session, card.id, first.id)
    with pytest.raises(TransformLimitReached):
        await card_service.grant_card(session, card.id, second.id)

    await card_service.revoke_card(session, card.id, first.id)
    await card_service.grant_card(session, card.id, second.id)

    assert await cards_crud.count_owners(session, card.id) == 1
    assert card.copies_count == 1


@pytest.mark.asyncio
async def test_limit_cannot_be_lower_than_live_copies(session):
    first = await characters_crud.create(session, vk_id=1, name="Первый")
    second = await characters_crud.create(session, vk_id=2, name="Второй")
    card = await card_service.create_card(
        session,
        name="Две копии",
        card_type=CardType.SPECIAL,
        kind="Особая",
        rarity=Rarity.A,
        admin_vk_id=99,
        number=18,
        transform_limit=2,
    )
    await card_service.grant_card(session, card.id, first.id)
    await card_service.grant_card(session, card.id, second.id)

    with pytest.raises(ValidationError, match="живых копий уже 2"):
        await card_service.update_card(session, card.id, transform_limit=1)


@pytest.mark.asyncio
async def test_special_slot_number_must_be_unique_and_between_zero_and_99(session):
    await card_service.create_card(
        session,
        name="Нулевая",
        card_type=CardType.SPECIAL,
        kind="Особая",
        rarity=Rarity.SS,
        admin_vk_id=99,
        number=0,
    )

    with pytest.raises(ValidationError, match="уже занят"):
        await card_service.create_card(
            session,
            name="Дубликат",
            card_type=CardType.SPECIAL,
            kind="Особая",
            rarity=Rarity.S,
            admin_vk_id=99,
            number=0,
        )

    with pytest.raises(ValidationError, match="от 0 до 99"):
        await card_service.create_card(
            session,
            name="Сотая",
            card_type=CardType.SPECIAL,
            kind="Особая",
            rarity=Rarity.S,
            admin_vk_id=99,
            number=100,
        )


@pytest.mark.asyncio
async def test_card_search_is_case_insensitive_for_cyrillic(session):
    await card_service.create_card(
        session,
        name="Тестовая Карта",
        card_type=CardType.SPELL,
        kind="Заклинание",
        rarity=Rarity.H,
        admin_vk_id=99,
    )

    card = await card_service.find_card(session, "тЕсТоВаЯ кАрТа")

    assert card.name == "Тестовая Карта"


@pytest.mark.asyncio
async def test_character_can_hold_several_physical_copies_of_same_card(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    card = await card_service.create_card(
        session,
        name="Пепел",
        card_type=CardType.SPELL,
        kind="Заклинание",
        rarity=Rarity.H,
        admin_vk_id=99,
    )

    first = await card_service.grant_card(session, card.id, character.id)
    second = await card_service.grant_card(session, card.id, character.id)

    assert first.id != second.id
    assert await cards_crud.count_owners(session, card.id) == 2


@pytest.mark.asyncio
async def test_ordinary_card_is_stored_only_on_character_ownership(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")

    ownership = await card_service.grant_ordinary_card(
        session,
        character_id=character.id,
        name="Верёвка",
        kind="Инструмент",
        rarity=Rarity.H,
        description="Обычная верёвка",
    )

    assert ownership.card_id is None
    assert ownership.display_type is CardType.ORDINARY
    assert ownership.display_name == "Верёвка"
    assert await cards_crud.count_cards(session) == 0


@pytest.mark.asyncio
async def test_spell_and_contour_share_public_id_pool_from_one_hundred(session):
    spell = await card_service.create_card(
        session,
        name="Искра",
        card_type=CardType.SPELL,
        kind="Заклинание",
        rarity=Rarity.H,
        admin_vk_id=99,
    )
    contour = await card_service.create_card(
        session,
        name="Покров",
        card_type=CardType.CONTOUR,
        kind="Форма — Покров",
        rarity=Rarity.H,
        admin_vk_id=99,
    )

    assert (spell.registry_number, contour.registry_number) == (100, 101)


@pytest.mark.asyncio
async def test_non_special_card_cannot_receive_special_fields_on_update(session):
    card = await card_service.create_card(
        session,
        name="Искра",
        card_type=CardType.SPELL,
        kind="Заклинание",
        rarity=Rarity.H,
        admin_vk_id=99,
    )

    with pytest.raises(ValidationError, match="только для Особой"):
        await card_service.update_card(session, card.id, number=12)
    with pytest.raises(ValidationError, match="только Особым"):
        await card_service.update_card(session, card.id, transform_limit=2)


@pytest.mark.asyncio
async def test_special_card_cannot_lose_slot_number(session):
    card = await card_service.create_card(
        session,
        name="Слот",
        card_type=CardType.SPECIAL,
        kind="Предмет",
        rarity=Rarity.H,
        admin_vk_id=99,
        number=7,
    )

    with pytest.raises(ValidationError, match="должна иметь номер"):
        await card_service.update_card(session, card.id, number=None)


@pytest.mark.asyncio
async def test_registered_copies_can_be_granted_and_partially_revoked(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    card = await card_service.create_card(
        session,
        name="Искры",
        card_type=CardType.SPELL,
        kind="Заклинание",
        rarity=Rarity.H,
        admin_vk_id=99,
    )

    granted = await card_service.grant_card_copies(
        session, card.id, character.id, quantity=5
    )
    revoked = await card_service.revoke_card_copies(
        session, card.id, character.id, quantity=2
    )

    assert len(granted) == 5
    assert len(revoked) == 2
    assert await cards_crud.count_owners(session, card.id) == 3
    assert card.copies_count == 3


@pytest.mark.asyncio
async def test_ordinary_copies_can_be_partially_revoked(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    await card_service.grant_ordinary_cards(
        session,
        character_id=character.id,
        name="Яблоко",
        kind="Еда",
        rarity=Rarity.H,
        quantity=4,
    )

    await card_service.revoke_ordinary_cards(
        session, character_id=character.id, name="Яблоко", quantity=2
    )
    ownerships = await cards_crud.list_character_ownerships(session, character.id)

    assert [item.display_name for item in ownerships] == ["Яблоко", "Яблоко"]


@pytest.mark.asyncio
async def test_consumption_removes_exact_quantity_and_writes_audit(session):
    character = await characters_crud.create(session, vk_id=101, name="Ава")
    card = await card_service.create_card(
        session,
        name="Перенос",
        card_type=CardType.SPELL,
        kind="Заклинание",
        rarity=Rarity.H,
        admin_vk_id=99,
    )
    await card_service.grant_card_copies(
        session, card.id, character.id, quantity=3
    )

    result = await card_service.consume_card(
        session,
        character_id=character.id,
        used_by_vk_id=101,
        name="Перенос",
        quantity=2,
        target_vk_id=202,
        peer_id=2_000_000_001,
        conversation_message_id=77,
    )
    usage = await session.scalar(select(CardUsage))

    assert result.quantity == 2
    assert result.remaining_free == 1
    assert await cards_crud.count_owners(session, card.id) == 1
    assert usage is not None
    assert usage.id == result.usage_id
    assert len(usage.ownership_ids) == 2
    assert usage.target_vk_id == 202


@pytest.mark.asyncio
async def test_consumption_is_atomic_when_quantity_is_insufficient(session):
    character = await characters_crud.create(session, vk_id=101, name="Ава")
    await card_service.grant_ordinary_cards(
        session,
        character_id=character.id,
        name="Яблоко",
        kind="Еда",
        rarity=Rarity.H,
        quantity=2,
    )

    with pytest.raises(ValidationError, match="только 2"):
        await card_service.consume_card(
            session,
            character_id=character.id,
            used_by_vk_id=101,
            name="Яблоко",
            quantity=3,
            target_vk_id=202,
            peer_id=2_000_000_001,
            conversation_message_id=77,
        )

    assert len(await cards_crud.list_character_ownerships(session, character.id)) == 2
