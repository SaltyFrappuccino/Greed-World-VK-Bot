import hashlib
import logging
from io import BytesIO
from pathlib import Path

from aiohttp import FormData
from PIL import Image, ImageOps

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
    log_context: str | None = None,
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
    upload_id = hashlib.sha256(data).hexdigest()[:12]
    width, height, image_format = _image_info(data)
    attempts = [(data, safe_name, mime), (data, safe_name, mime)]
    jpeg = _as_jpeg(data)
    if jpeg is not None:
        attempts.append((jpeg, f"{Path(safe_name).stem}.jpg", "image/jpeg"))
    logger.info(
        "vk_photo.prepare upload_id=%s context=%s peer_id=%s filename=%s "
        "bytes=%s mime=%s width=%s height=%s format=%s attempts=%s",
        upload_id,
        log_context or "unspecified",
        peer_id,
        safe_name,
        len(data),
        mime,
        width,
        height,
        image_format,
        len(attempts),
    )

    uploaded = None
    photo_payload = None
    last_error: Exception | None = None
    attempt_results: list[str] = []
    for attempt, (attempt_data, attempt_name, attempt_mime) in enumerate(
        attempts, start=1
    ):
        logger.info(
            "vk_photo.attempt upload_id=%s context=%s attempt=%s/%s "
            "filename=%s bytes=%s mime=%s",
            upload_id,
            log_context or "unspecified",
            attempt,
            len(attempts),
            attempt_name,
            len(attempt_data),
            attempt_mime,
        )
        try:
            server_response = await api.request(
                "photos.getMessagesUploadServer", {"peer_id": peer_id}
            )
            upload_url = server_response["response"]["upload_url"]
        except Exception as error:
            last_error = error
            attempt_results.append(f"{attempt}:get_server_error:{type(error).__name__}")
            logger.exception(
                "vk_photo.get_server_failed upload_id=%s context=%s "
                "peer_id=%s attempt=%s/%s error_type=%s",
                upload_id,
                log_context or "unspecified",
                peer_id,
                attempt,
                len(attempts),
                type(error).__name__,
            )
            continue
        form = FormData()
        form.add_field(
            "photo",
            attempt_data,
            filename=attempt_name,
            content_type=attempt_mime,
        )
        try:
            uploaded = await api.http_client.request_json(
                upload_url,
                method="POST",
                data=form,
            )
        except Exception as error:
            last_error = error
            attempt_results.append(f"{attempt}:upload_error:{type(error).__name__}")
            logger.exception(
                "vk_photo.upload_failed upload_id=%s context=%s peer_id=%s "
                "attempt=%s/%s error_type=%s",
                upload_id,
                log_context or "unspecified",
                peer_id,
                attempt,
                len(attempts),
                type(error).__name__,
            )
            continue
        if not isinstance(uploaded, dict):
            attempt_results.append(
                f"{attempt}:invalid_response:{type(uploaded).__name__}"
            )
            logger.warning(
                "vk_photo.invalid_upload_response upload_id=%s context=%s "
                "attempt=%s/%s response_type=%s",
                upload_id,
                log_context or "unspecified",
                attempt,
                len(attempts),
                type(uploaded).__name__,
            )
            uploaded = None
            continue
        photo_payload = _uploaded_photo_payload(uploaded.get("photo"))
        if photo_payload is not None:
            attempt_results.append(f"{attempt}:uploaded")
            logger.info(
                "vk_photo.uploaded upload_id=%s context=%s attempt=%s/%s "
                "response=%s",
                upload_id,
                log_context or "unspecified",
                attempt,
                len(attempts),
                _upload_response_summary(uploaded),
            )
            break
        attempt_results.append(f"{attempt}:empty_photo")
        logger.warning(
            "vk_photo.empty_upload_response upload_id=%s context=%s peer_id=%s "
            "attempt=%s/%s response=%s",
            upload_id,
            log_context or "unspecified",
            peer_id,
            attempt,
            len(attempts),
            _upload_response_summary(uploaded),
        )
    if uploaded is None or photo_payload is None:
        logger.error(
            "vk_photo.failed upload_id=%s context=%s peer_id=%s filename=%s "
            "attempts=%s results=%s last_error_type=%s",
            upload_id,
            log_context or "unspecified",
            peer_id,
            safe_name,
            len(attempts),
            ",".join(attempt_results),
            type(last_error).__name__ if last_error is not None else None,
        )
        raise ServiceError(
            "VK не принял изображение после повторных попыток. "
            "Подробности записаны в лог."
        ) from last_error

    try:
        saved_response = await api.request(
            "photos.saveMessagesPhoto",
            {
                "server": uploaded.get("server"),
                "photo": photo_payload,
                "hash": uploaded.get("hash"),
            },
        )
    except Exception as error:
        logger.exception(
            "vk_photo.save_failed upload_id=%s context=%s peer_id=%s "
            "error_type=%s upload_response=%s",
            upload_id,
            log_context or "unspecified",
            peer_id,
            type(error).__name__,
            _upload_response_summary(uploaded),
        )
        raise ServiceError(
            "VK принял файл, но не смог сохранить изображение. "
            "Подробности записаны в лог."
        ) from error
    saved = saved_response.get("response") if isinstance(saved_response, dict) else None
    if not saved:
        logger.error(
            "vk_photo.empty_save_response upload_id=%s context=%s peer_id=%s "
            "response=%s",
            upload_id,
            log_context or "unspecified",
            peer_id,
            _save_response_summary(saved_response),
        )
        raise ServiceError("VK не вернул сохранённое изображение.")
    if (
        not isinstance(saved, list)
        or not isinstance(saved[0], dict)
        or saved[0].get("owner_id") is None
        or saved[0].get("id") is None
    ):
        logger.error(
            "vk_photo.invalid_saved_photo upload_id=%s context=%s peer_id=%s "
            "response=%s",
            upload_id,
            log_context or "unspecified",
            peer_id,
            _save_response_summary(saved_response),
        )
        raise ServiceError("VK вернул некорректные данные изображения.")
    photo = saved[0]
    access_key = photo.get("access_key")
    suffix = f"_{access_key}" if access_key else ""
    attachment = f"photo{photo['owner_id']}_{photo['id']}{suffix}"
    logger.info(
        "vk_photo.success upload_id=%s context=%s peer_id=%s attachment_owner=%s "
        "attachment_id=%s access_key=%s",
        upload_id,
        log_context or "unspecified",
        peer_id,
        photo["owner_id"],
        photo["id"],
        bool(access_key),
    )
    return attachment


def _uploaded_photo_payload(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    payload = value.strip()
    if not payload or payload in {"[]", "{}", "null"}:
        return None
    return payload


def _as_jpeg(data: bytes) -> bytes | None:
    try:
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
    except (OSError, ValueError):
        return None


def _image_info(data: bytes) -> tuple[int | None, int | None, str | None]:
    try:
        with Image.open(BytesIO(data)) as image:
            return image.width, image.height, image.format
    except (OSError, ValueError):
        return None, None, None


def _upload_response_summary(response: dict[str, object]) -> str:
    raw_photo = response.get("photo")
    error = response.get("error")
    if isinstance(error, dict):
        error_summary = {
            key: str(error[key])[:200]
            for key in ("error_code", "error_msg")
            if key in error
        }
    elif error is not None:
        error_summary = str(error)[:200]
    else:
        error_summary = None
    return (
        f"keys={','.join(sorted(response))};"
        f"photo_type={type(raw_photo).__name__};"
        f"photo_length={len(raw_photo) if hasattr(raw_photo, '__len__') else None};"
        f"server_present={response.get('server') is not None};"
        f"hash_present={bool(response.get('hash'))};"
        f"error={error_summary}"
    )


def _save_response_summary(response: object) -> str:
    if not isinstance(response, dict):
        return f"type={type(response).__name__}"
    saved = response.get("response")
    return (
        f"keys={','.join(sorted(response))};"
        f"response_type={type(saved).__name__};"
        f"response_length={len(saved) if hasattr(saved, '__len__') else None}"
    )


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
