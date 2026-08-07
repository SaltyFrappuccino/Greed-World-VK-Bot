import logging
import re

import pytest
from aiohttp import FormData
from io import BytesIO
from PIL import Image

from bot.services.errors import ServiceError
from bot.utils.photos import upload_message_photo


class FakeHTTPClient:
    def __init__(self, response):
        self.responses = response if isinstance(response, list) else [response]
        self.calls = []

    async def request_json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]


class FakeAPI:
    def __init__(self, upload_response, *, save_response=None):
        self.http_client = FakeHTTPClient(upload_response)
        self.calls = []
        self.save_response = save_response

    async def request(self, method, params):
        self.calls.append((method, params))
        if method == "photos.getMessagesUploadServer":
            return {"response": {"upload_url": "https://upload.test/photo"}}
        if method == "photos.saveMessagesPhoto":
            if self.save_response is not None:
                return self.save_response
            return {
                "response": [
                    {"owner_id": -42, "id": 17, "access_key": "secret"}
                ]
            }
        raise AssertionError(f"Unexpected API method: {method}")


@pytest.mark.asyncio
async def test_upload_message_photo_uses_explicit_multipart():
    api = FakeAPI({"server": 123, "photo": "encoded", "hash": "hash"})

    attachment = await upload_message_photo(
        api,
        2_000_000_001,
        b"\x89PNG\r\n\x1a\nimage",
        filename="profile.png",
    )

    assert attachment == "photo-42_17_secret"
    assert api.calls == [
        ("photos.getMessagesUploadServer", {"peer_id": 2_000_000_001}),
        (
            "photos.saveMessagesPhoto",
            {"server": 123, "photo": "encoded", "hash": "hash"},
        ),
    ]
    _, upload_kwargs = api.http_client.calls[0]
    assert upload_kwargs["method"] == "POST"
    assert isinstance(upload_kwargs["data"], FormData)
    assert upload_kwargs["data"].is_multipart
    disposition, headers, payload = upload_kwargs["data"]._fields[0]
    assert disposition["name"] == "photo"
    assert disposition["filename"] == "profile.png"
    assert headers["Content-Type"] == "image/png"
    assert payload.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_upload_message_photo_rejects_empty_vk_upload_response():
    api = FakeAPI({"server": 123, "photo": "", "hash": "hash"})

    with pytest.raises(ServiceError, match="VK не принял изображение"):
        await upload_message_photo(api, 10, b"\xff\xd8\xffimage")

    assert [method for method, _ in api.calls] == [
        "photos.getMessagesUploadServer",
        "photos.getMessagesUploadServer",
    ]


@pytest.mark.asyncio
async def test_upload_failure_logs_safe_diagnostics(caplog):
    api = FakeAPI(
        {"server": 123, "photo": "", "hash": "private-hash", "extra": "secret"}
    )

    with caplog.at_level(logging.INFO, logger="bot.utils.photos"):
        with pytest.raises(ServiceError):
            await upload_message_photo(
                api,
                2_000_000_001,
                b"not-a-real-jpeg",
                filename="profile_card_5.png",
                content_type="image/png",
                log_context="profile_card:5",
            )

    log = caplog.text
    assert "vk_photo.prepare" in log
    assert "context=profile_card:5" in log
    assert "peer_id=2000000001" in log
    assert "filename=profile_card_5.png" in log
    assert "bytes=15" in log
    assert "mime=image/png" in log
    assert "attempt=1/2" in log
    assert "attempt=2/2" in log
    assert "photo_type=str" in log
    assert "photo_length=0" in log
    assert "results=1:empty_photo,2:empty_photo" in log
    assert "private-hash" not in log
    assert "secret" not in log
    upload_ids = re.findall(r"upload_id=([0-9a-f]{12})", log)
    assert len(upload_ids) >= 5
    assert len(set(upload_ids)) == 1


@pytest.mark.asyncio
async def test_empty_save_response_logs_distinct_stage(caplog):
    api = FakeAPI(
        {"server": 123, "photo": "encoded", "hash": "private-hash"},
        save_response={"response": []},
    )

    with caplog.at_level(logging.INFO, logger="bot.utils.photos"):
        with pytest.raises(ServiceError):
            await upload_message_photo(
                api,
                2_000_000_002,
                b"not-a-real-jpeg",
                filename="profile_card_8.png",
                log_context="profile_card:8",
            )

    log = caplog.text
    assert "vk_photo.uploaded" in log
    assert "vk_photo.empty_save_response" in log
    assert "context=profile_card:8" in log
    assert "response=keys=response;response_type=list;response_length=0" in log
    assert "private-hash" not in log


@pytest.mark.asyncio
async def test_invalid_saved_photo_is_logged_before_accessing_fields(caplog):
    api = FakeAPI(
        {"server": 123, "photo": "encoded", "hash": "hash"},
        save_response={"response": [{"id": 17}]},
    )

    with caplog.at_level(logging.INFO, logger="bot.utils.photos"):
        with pytest.raises(ServiceError):
            await upload_message_photo(
                api,
                2_000_000_003,
                b"not-a-real-jpeg",
                log_context="profile_card:9",
            )

    assert "vk_photo.invalid_saved_photo" in caplog.text
    assert "context=profile_card:9" in caplog.text
    assert "response_type=list;response_length=1" in caplog.text


@pytest.mark.asyncio
async def test_upload_message_photo_retries_empty_vk_response():
    api = FakeAPI(
        [
            {"server": 123, "photo": "", "hash": "hash"},
            {"server": 124, "photo": "encoded", "hash": "hash2"},
        ]
    )

    attachment = await upload_message_photo(
        api, 2_000_000_001, b"\xff\xd8\xffimage", filename="profile.jpg"
    )

    assert attachment == "photo-42_17_secret"
    assert [method for method, _ in api.calls] == [
        "photos.getMessagesUploadServer",
        "photos.getMessagesUploadServer",
        "photos.saveMessagesPhoto",
    ]


@pytest.mark.asyncio
async def test_upload_message_photo_falls_back_to_jpeg():
    source = BytesIO()
    Image.new("RGBA", (20, 30), (10, 20, 30, 128)).save(source, format="PNG")
    api = FakeAPI(
        [
            {"server": 123, "photo": "", "hash": "hash"},
            {"server": 124, "photo": "[]", "hash": "hash2"},
            {"server": 125, "photo": "encoded-jpeg", "hash": "hash3"},
        ]
    )

    attachment = await upload_message_photo(
        api, 2_000_000_001, source.getvalue(), filename="profile.png"
    )

    assert attachment == "photo-42_17_secret"
    _, third_upload = api.http_client.calls[2]
    disposition, headers, payload = third_upload["data"]._fields[0]
    assert disposition["filename"] == "profile.jpg"
    assert headers["Content-Type"] == "image/jpeg"
    assert payload.startswith(b"\xff\xd8\xff")
