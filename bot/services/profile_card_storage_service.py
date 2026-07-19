from pathlib import Path

from sqlalchemy.orm import Session

from bot.config import get_settings
from bot.services import art_storage_service
from bot.services.errors import ServiceError, ValidationError


def save_png(
    data: bytes, *, character_id: int, input_hash: str, session: Session
) -> tuple[str, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("Генератор профиля вернул некорректный PNG.")
    relative = Path(str(character_id)) / f"{input_hash}.png"
    target = _safe_path(relative.as_posix())
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".png.tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(target)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ServiceError(f"Не удалось сохранить визитку персонажа: {error}") from error
    art_storage_service.track_created_path(session, target)
    return relative.as_posix(), len(data)


def read_bytes(storage_key: str) -> bytes:
    path = _safe_path(storage_key)
    try:
        return path.read_bytes()
    except OSError as error:
        raise ServiceError(f"Сохранённая визитка недоступна: {error}") from error


def exists(storage_key: str) -> bool:
    return _safe_path(storage_key).is_file()


def schedule_delete(session: Session, storage_key: str) -> None:
    art_storage_service.schedule_path_delete(session, _safe_path(storage_key))


def _safe_path(storage_key: str) -> Path:
    root = get_settings().profile_card_storage_path
    path = (root / storage_key).resolve()
    if path != root and root not in path.parents:
        raise ValidationError("Некорректный путь сохранённой визитки.")
    return path
