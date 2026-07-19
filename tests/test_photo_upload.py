import pytest
from aiohttp import FormData

from bot.services.errors import ServiceError
from bot.utils.photos import upload_message_photo


class FakeHTTPClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def request_json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class FakeAPI:
    def __init__(self, upload_response):
        self.http_client = FakeHTTPClient(upload_response)
        self.calls = []

    async def request(self, method, params):
        self.calls.append((method, params))
        if method == "photos.getMessagesUploadServer":
            return {"response": {"upload_url": "https://upload.test/photo"}}
        if method == "photos.saveMessagesPhoto":
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
        "photos.getMessagesUploadServer"
    ]
