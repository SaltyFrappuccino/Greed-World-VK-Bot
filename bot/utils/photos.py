import logging
from pathlib import Path

from aiohttp import FormData

from bot.database.models import CharacterArt
from bot.services import art_storage_service
from bot.services.errors import ServiceError, ValidationError

logger = logging.getLogger(__name__)


def largest_photo_url(photo: object) -> str:
    sizes = [size for size in (getattr(photo, "sizes", None) or []) if size.url]
    original = getattr(photo, "orig_photo", None)
    if original is not None and original.url:
        sizes.append(original)
    if sizes:
        return str(max(sizes, key=lambda size: size.width * size.height).url)
    fallback = getattr(photo, "photo_256", None)
    if fallback:
        return str(fallback)
    raise ValidationError("VK не передал ссылку на изображение.")


def vk_photo_attachment(photo: object) -> str | None:
    owner_id = getattr(photo, "owner_id", None)
    photo_id = getattr(photo, "id", None)
    if owner_id is None or photo_id is None:
        return None
    access_key = getattr(photo, "access_key", None)
    suffix = f"_{access_key}" if access_key else ""
    return f"photo{owner_id}_{photo_id}{suffix}"


async def art_attachment(message, art: CharacterArt) -> str:
    if art.vk_attachment:
        return art.vk_attachment
    return await upload_message_photo(
        message.ctx_api,
        message.peer_id,
        art_storage_service.read_bytes(art.storage_key),
        filename=Path(art.storage_key).name,
        content_type=art.mime_type,
    )


async def upload_message_photo(
    api,
    peer_id: int,
    data: bytes,
    *,
    filename: str = "photo.jpg",
    content_type: str | None = None,
) -> str:
    """Upload an image to VK messages using an explicit multipart body.

    PhotoMessageUploader passes a file-like object through a generic mapping.
    With the currently installed aiohttp/vkbottle combination VK can receive an
    empty ``photo`` field.  Building FormData explicitly preserves the filename
    and MIME type expected by VK's upload server.
    """
    if not data:
        raise ServiceError("Нельзя отправить пустое изображение.")

    safe_name = Path(filename).name or "photo.jpg"
    mime = content_type or _content_type(data, safe_name)
    server_response = await api.request(
        "photos.getMessagesUploadServer", {"peer_id": peer_id}
    )
    upload_url = server_response["response"]["upload_url"]

    form = FormData()
    form.add_field(
        "photo",
        data,
        filename=safe_name,
        content_type=mime,
    )
    uploaded = await api.http_client.request_json(
        upload_url,
        method="POST",
        data=form,
    )
    if not uploaded.get("photo"):
        logger.error(
            "VK photo upload returned no photo: peer_id=%s filename=%s response_keys=%s",
            peer_id,
            safe_name,
            sorted(uploaded),
        )
        raise ServiceError("VK не принял изображение. Подробности записаны в лог.")

    saved_response = await api.request(
        "photos.saveMessagesPhoto",
        {
            "server": uploaded.get("server"),
            "photo": uploaded["photo"],
            "hash": uploaded.get("hash"),
        },
    )
    saved = saved_response.get("response") or []
    if not saved:
        raise ServiceError("VK не вернул сохранённое изображение.")
    photo = saved[0]
    access_key = photo.get("access_key")
    suffix = f"_{access_key}" if access_key else ""
    return f"photo{photo['owner_id']}_{photo['id']}{suffix}"


def _content_type(data: bytes, filename: str) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    suffix = Path(filename).suffix.lower()
    return {
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")
