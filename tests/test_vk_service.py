import pytest

from bot.services.vk_service import resolve_user_id
from bot.utils.validators import extract_vk_profile_urls, parse_vk_reference


class _UsersAPI:
    async def get(self, *, user_ids):
        assert user_ids == ["sword_saint"]
        return [type("User", (), {"id": 564059694})()]


class _API:
    users = _UsersAPI()


def test_short_vk_url_is_parsed_as_screen_name():
    assert parse_vk_reference("https://vk.ru/sword_saint") == "sword_saint"


@pytest.mark.asyncio
async def test_short_vk_url_is_resolved_through_api():
    assert await resolve_user_id(_API(), "https://vk.ru/sword_saint") == 564059694


def test_short_vk_url_is_extracted_from_long_message():
    assert extract_vk_profile_urls(
        "Создай анкету для https://vk.ru/idi_nahuy_dayn_tupoi. Вот текст"
    ) == ["https://vk.ru/idi_nahuy_dayn_tupoi"]
