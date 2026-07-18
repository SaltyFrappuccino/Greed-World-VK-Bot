import pytest

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import CardType, Rarity
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
async def test_spell_and_contour_share_number_pool_from_zero(session):
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

    assert (spell.registry_number, contour.registry_number) == (0, 1)


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
