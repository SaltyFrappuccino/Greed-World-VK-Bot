import asyncio
import hashlib
import shutil
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy import event
from sqlalchemy.orm import Session

from bot.config import get_settings
from bot.services.errors import ServiceError, ValidationError

ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}
ALLOWED_VK_HOST_SUFFIXES = (".userapi.com", ".vkuserphoto.ru", ".vk.com")
MAX_PIXELS = 50_000_000
_CREATED_KEY = "character_art_created_paths"
_DELETE_KEY = "character_art_delete_after_commit"


@dataclass(frozen=True)
class StoredArt:
    storage_key: str
    sha256: str
    mime_type: str
    file_size: int
    width: int
    height: int


async def download_and_store(
    source_url: str, *, character_id: int, session: Session
) -> StoredArt:
    _validate_source_url(source_url)
    settings = get_settings()
    data = await _download(source_url, settings.character_art_max_file_bytes)
    return await asyncio.to_thread(
        store_bytes,
        data,
        character_id=character_id,
        session=session,
    )


def store_bytes(data: bytes, *, character_id: int, session: Session) -> StoredArt:
    settings = get_settings()
    if not data:
        raise ValidationError("Получено пустое изображение.")
    if len(data) > settings.character_art_max_file_bytes:
        raise ValidationError(
            f"Изображение больше допустимых {settings.character_art_max_file_bytes // 1024 // 1024} МБ."
        )
    image_format, width, height = _inspect_image(data)
    mime_type, extension = ALLOWED_FORMATS[image_format]
    root = settings.character_art_storage_path
    used = _directory_size(root)
    free = shutil.disk_usage(root.parent if root.parent.exists() else root.anchor).free
    if used + len(data) > settings.character_art_max_total_bytes:
        raise ValidationError("Локальное хранилище артов достигло настроенного лимита.")
    if free < len(data) + 50 * 1024 * 1024:
        raise ValidationError("На диске недостаточно свободного места для сохранения арта.")

    relative = Path("characters") / str(character_id) / f"{uuid4().hex}{extension}"
    target = _safe_path(relative.as_posix())
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ServiceError(f"Не удалось сохранить арт: {error}") from error
    track_created_path(session, target)
    return StoredArt(
        storage_key=relative.as_posix(),
        sha256=hashlib.sha256(data).hexdigest(),
        mime_type=mime_type,
        file_size=len(data),
        width=width,
        height=height,
    )


def read_bytes(storage_key: str) -> bytes:
    path = _safe_path(storage_key)
    try:
        return path.read_bytes()
    except OSError as error:
        raise ServiceError(f"Файл арта недоступен: {error}") from error


def thumbnail_bytes(storage_key: str, *, max_side: int = 800) -> bytes:
    try:
        with Image.open(BytesIO(read_bytes(storage_key))) as image:
            image.thumbnail((max_side, max_side))
            if image.mode not in {"RGB", "L"}:
                background = Image.new("RGB", image.size, "white")
                if "A" in image.getbands():
                    background.paste(image, mask=image.getchannel("A"))
                else:
                    background.paste(image)
                image = background
            elif image.mode == "L":
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=82, optimize=True)
            return output.getvalue()
    except ServiceError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ServiceError(f"Не удалось подготовить превью арта: {error}") from error


def schedule_delete(session: Session, storage_key: str) -> None:
    path = _safe_path(storage_key)
    schedule_path_delete(session, path)


def track_created_path(session: Session, path: Path) -> None:
    session.info.setdefault(_CREATED_KEY, set()).add(str(path.resolve()))


def schedule_path_delete(session: Session, path: Path) -> None:
    session.info.setdefault(_DELETE_KEY, set()).add(str(path.resolve()))


def _safe_path(storage_key: str) -> Path:
    root = get_settings().character_art_storage_path
    path = (root / storage_key).resolve()
    if path != root and root not in path.parents:
        raise ValidationError("Некорректный путь локального арта.")
    return path


async def _download(url: str, limit: int) -> bytes:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                _validate_source_url(str(response.url))
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > limit:
                    raise ValidationError("Изображение превышает допустимый размер.")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > limit:
                        raise ValidationError("Изображение превышает допустимый размер.")
                    chunks.append(chunk)
                return b"".join(chunks)
    except ValidationError:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise ServiceError(f"Не удалось скачать изображение из VK: {error}") from error


def _inspect_image(data: bytes) -> tuple[str, int, int]:
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
            if image_format not in ALLOWED_FORMATS:
                raise ValidationError("Поддерживаются только JPEG, PNG и WebP.")
            if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                raise ValidationError("Недопустимые размеры изображения.")
            image.verify()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValidationError("Вложение не является корректным изображением.") from error
    return image_format, width, height


def _validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not any(
        hostname.endswith(suffix) for suffix in ALLOWED_VK_HOST_SUFFIXES
    ):
        raise ValidationError("Разрешены только HTTPS-изображения из вложений VK.")


def _directory_size(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    session.info.pop(_CREATED_KEY, None)
    for raw_path in session.info.pop(_DELETE_KEY, set()):
        Path(raw_path).unlink(missing_ok=True)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_DELETE_KEY, None)
    for raw_path in session.info.pop(_CREATED_KEY, set()):
        Path(raw_path).unlink(missing_ok=True)
