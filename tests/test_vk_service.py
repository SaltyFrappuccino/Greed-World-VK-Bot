import pytest

from bot.services.vk_service import resolve_user_id
from bot.utils.validators import parse_vk_reference


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
