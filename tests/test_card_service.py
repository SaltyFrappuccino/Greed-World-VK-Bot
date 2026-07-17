import pytest

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import Rarity
from bot.services import card_service
from bot.services.errors import TransformLimitReached, ValidationError


@pytest.mark.asyncio
async def test_transform_limit_is_freed_after_revoke(session):
    first = await characters_crud.create(session, vk_id=1, name="Первый")
    second = await characters_crud.create(session, vk_id=2, name="Второй")
    card = await card_service.create_card(
        session,
        name="Ясень",
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
        kind="Особая",
        rarity=Rarity.A,
        admin_vk_id=99,
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
        kind="Особая",
        rarity=Rarity.SS,
        admin_vk_id=99,
        number=0,
    )

    with pytest.raises(ValidationError, match="уже занят"):
        await card_service.create_card(
            session,
            name="Дубликат",
            kind="Особая",
            rarity=Rarity.S,
            admin_vk_id=99,
            number=0,
        )

    with pytest.raises(ValidationError, match="от 0 до 99"):
        await card_service.create_card(
            session,
            name="Сотая",
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
        kind="Обычная",
        rarity=Rarity.H,
        admin_vk_id=99,
    )

    card = await card_service.find_card(session, "тЕсТоВаЯ кАрТа")

    assert card.name == "Тестовая Карта"
