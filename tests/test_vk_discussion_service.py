from types import SimpleNamespace

import pytest

from bot.services import vk_discussion_service as service
from bot.services.errors import ValidationError


def test_parse_topic_url():
    assert service.parse_topic_url(
        "https://vk.ru/topic-240214251_68811646"
    ) == (240214251, 68811646)


def test_parse_topic_url_rejects_unrelated_url():
    with pytest.raises(ValidationError, match="Ссылка на обсуждение"):
        service.parse_topic_url("https://vk.ru/wall-1_2")


@pytest.mark.asyncio
async def test_list_applications_reads_authors_text_and_largest_photo(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(
            vk_board_token="service-token",
            vk_applications_topic_url="https://vk.ru/topic-240214251_68811646",
        ),
    )

    async def fake_request(_params):
        return {
            "response": {
                "count": 1,
                "profiles": [
                    {
                        "id": 485208149,
                        "first_name": "Слава",
                        "last_name": "Игрок",
                        "screen_name": "slava",
                    }
                ],
                "items": [
                    {
                        "id": 77,
                        "from_id": 485208149,
                        "date": 12345,
                        "text": "❖ Основное\n➤ Пикколо",
                        "attachments": [
                            {
                                "type": "photo",
                                "photo": {
                                    "id": 9,
                                    "owner_id": 485208149,
                                    "access_key": "key",
                                    "sizes": [
                                        {"url": "small", "width": 100, "height": 100},
                                        {"url": "large", "width": 900, "height": 1400},
                                    ],
                                },
                            }
                        ],
                    }
                ],
            }
        }

    monkeypatch.setattr(service, "_request", fake_request)

    total, applications = await service.list_applications()

    assert total == 1
    application = applications[0]
    assert application.comment_id == 77
    assert application.author_vk_id == 485208149
    assert application.author_name == "Слава Игрок"
    assert application.author_url == "https://vk.ru/id485208149"
    assert application.photos[0].url == "large"
    assert application.photos[0].attachment == "photo485208149_9_key"
    assert len(application.content_hash) == 64
