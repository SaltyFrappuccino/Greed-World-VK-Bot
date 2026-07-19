from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from bot.database.crud import characters as characters_crud
from bot.services import profile_card_service, profile_card_storage_service
from bot.services.profile_card_renderer import (
    RATING_COLORS,
    STAT_LABELS,
    ProfileCardData,
    render_profile_card,
)


def _small_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (40, 50), "purple").save(output, format="PNG")
    return output.getvalue()


def test_renderer_creates_portrait_png_with_cyrillic() -> None:
    data = ProfileCardData(
        character_id=7,
        name="Пикколо",
        age=31,
        gender="Мужской",
        rating="H",
        shakei=67,
        stats={
            "stress_resistance": 4,
            "speech": 3,
            "intuition": 4,
            "spine": 5,
            "will": 3,
            "scent": 3,
        },
        skills=[f"Очень длинный навык персонажа номер {index}" for index in range(30)],
        card_counts={"Обычная": 3, "Заклинание": 2},
        contours_used=1,
        contour_limit=2,
    )
    result = render_profile_card(data, None)
    with Image.open(BytesIO(result)) as image:
        assert image.format == "PNG"
        assert image.size == (1200, 1600)


def test_each_stat_and_rating_has_its_own_color() -> None:
    assert len({color for _, _, color in STAT_LABELS}) == 6
    assert len(set(RATING_COLORS.values())) == len(RATING_COLORS)


@pytest.mark.asyncio
async def test_profile_card_cache_reuses_and_invalidates(
    session, tmp_path, monkeypatch
) -> None:
    settings = SimpleNamespace(profile_card_storage_path=tmp_path / "cards")
    monkeypatch.setattr(
        profile_card_storage_service, "get_settings", lambda: settings
    )
    calls = 0

    def fake_render(_data, _art):
        nonlocal calls
        calls += 1
        return _small_png()

    monkeypatch.setattr(profile_card_service, "render_profile_card", fake_render)
    character = await characters_crud.create(
        session,
        vk_id=100,
        name="Ава",
        skills="Тактик\nСледопыт",
        is_approved=True,
    )

    first = await profile_card_service.get_or_create(session, character.id)
    second = await profile_card_service.get_or_create(session, character.id)
    assert first.reused is False
    assert second.reused is True
    assert first.cache.input_hash == second.cache.input_hash
    first_hash = first.cache.input_hash
    assert calls == 1

    character.will = 4
    await session.flush()
    third = await profile_card_service.get_or_create(session, character.id)
    assert third.reused is False
    assert third.cache.input_hash != first_hash
    assert calls == 2


@pytest.mark.asyncio
async def test_vk_attachment_is_remembered_only_for_current_hash(
    session, tmp_path, monkeypatch
) -> None:
    settings = SimpleNamespace(profile_card_storage_path=tmp_path / "cards")
    monkeypatch.setattr(
        profile_card_storage_service, "get_settings", lambda: settings
    )
    monkeypatch.setattr(
        profile_card_service, "render_profile_card", lambda *_args: _small_png()
    )
    character = await characters_crud.create(session, vk_id=100, name="Ава")
    result = await profile_card_service.get_or_create(session, character.id)

    await profile_card_service.remember_vk_attachment(
        session,
        character_id=character.id,
        input_hash="неактуальный",
        attachment="photo1_1",
    )
    assert result.cache.vk_attachment is None
    await profile_card_service.remember_vk_attachment(
        session,
        character_id=character.id,
        input_hash=result.cache.input_hash,
        attachment="photo1_2",
    )
    assert result.cache.vk_attachment == "photo1_2"
