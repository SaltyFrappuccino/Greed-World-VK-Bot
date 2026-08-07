import asyncio
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bot.config import get_settings
from bot.database.engine import engine
from bot.services.errors import ServiceError, ValidationError


@dataclass(frozen=True)
class DatabaseBackup:
    filename: str
    data: bytes
    stored_path: Path | None = None


async def create_database_backup() -> DatabaseBackup:
    if engine.url.get_backend_name() != "sqlite":
        raise ValidationError(
            "Отправка БД файлом поддерживается только для SQLite. "
            "Для PostgreSQL нужен отдельный pg_dump."
        )
    database = engine.url.database
    if not database or database == ":memory:":
        raise ValidationError("Нельзя создать файловый бэкап базы в памяти.")
    return await create_sqlite_backup(
        Path(database), destination_dir=get_settings().backup_storage_path
    )


async def create_sqlite_backup(
    source_path: Path, *, destination_dir: Path | None = None
) -> DatabaseBackup:
    filename = f"zhadny_mir_backup_{datetime.now():%Y-%m-%d_%H-%M-%S}.db"
    try:
        return await asyncio.to_thread(
            _create_backup, source_path, filename, destination_dir
        )
    except (OSError, sqlite3.Error) as error:
        raise ServiceError(f"Не удалось создать бэкап БД: {error}") from error


def _create_backup(
    source_path: Path, filename: str, destination_dir: Path | None
) -> DatabaseBackup:
    if not source_path.is_file():
        raise OSError(f"файл базы не найден: {source_path}")

    if destination_dir is None:
        with tempfile.TemporaryDirectory(prefix="zhadny-mir-backup-") as temp_dir:
            return _write_backup(source_path, Path(temp_dir) / filename, filename, False)

    destination_dir.mkdir(parents=True, exist_ok=True)
    return _write_backup(source_path, destination_dir / filename, filename, True)


def _write_backup(
    source_path: Path, backup_path: Path, filename: str, persistent: bool
) -> DatabaseBackup:
    try:
        with closing(sqlite3.connect(source_path)) as source, closing(
            sqlite3.connect(backup_path)
        ) as target:
            source.backup(target)
            result = target.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise sqlite3.DatabaseError("проверка целостности бэкапа не пройдена")
        return DatabaseBackup(
            filename=filename,
            data=backup_path.read_bytes(),
            stored_path=backup_path if persistent else None,
        )
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise
