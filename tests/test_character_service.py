import pytest

from bot.database.crud import characters as characters_crud
from bot.database.models import Rarity
from bot.services import character_service
from bot.services.errors import ValidationError


@pytest.mark.asyncio
async def test_stats_use_one_to_five_scale_and_rating_uses_rarity(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")

    await character_service.set_stat(session, character.id, "чуйка", 5)
    await character_service.set_rating(session, character.id, Rarity.SS)

    assert character.intuition == 5
    assert character.overall_rating is Rarity.SS

    with pytest.raises(ValidationError, match="от 1 до 5"):
        await character_service.set_stat(session, character.id, "чуйка", 6)


@pytest.mark.asyncio
async def test_player_can_set_stats_only_before_approval(session):
    character = await characters_crud.create(session, vk_id=1, name="Игрок")

    await character_service.set_pending_stat(session, character, "воля", 4)
    assert character.will == 4

    await character_service.approve(session, character.id)
    with pytest.raises(ValidationError, match="корректирует администратор"):
        await character_service.set_pending_stat(session, character, "воля", 5)


@pytest.mark.asyncio
async def test_one_vk_account_can_own_multiple_characters(session):
    first = await character_service.create_character(session, vk_id=1, name="Первый")
    second = await character_service.create_character(session, vk_id=1, name="Второй")

    characters = await character_service.list_by_vk_id(session, 1)

    assert [character.name for character in characters] == ["Второй", "Первый"]
    assert await character_service.require_owned(
        session, character_id=second.id, vk_id=1
    ) is second
    with pytest.raises(ValidationError, match="несколько анкет"):
        await character_service.require_single_by_vk_id(session, 1)


@pytest.mark.asyncio
async def test_character_search_is_case_insensitive_for_cyrillic(session):
    await character_service.create_character(session, vk_id=1, name="Тихий Странник")

    character = await character_service.find_character(session, "тИхИй сТрАнНиК")

    assert character.name == "Тихий Странник"
