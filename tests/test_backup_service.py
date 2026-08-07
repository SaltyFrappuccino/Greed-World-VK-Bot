import sqlite3

import pytest

from bot.services import backup_service


@pytest.mark.asyncio
async def test_sqlite_backup_is_valid_and_contains_current_data(tmp_path):
    source_path = tmp_path / "source.db"
    with sqlite3.connect(source_path) as connection:
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.execute("INSERT INTO example VALUES ('Жадный Мир')")

    backup = await backup_service.create_sqlite_backup(source_path)

    restored = sqlite3.connect(":memory:")
    try:
        restored.deserialize(backup.data)
        value = restored.execute("SELECT value FROM example").fetchone()[0]
        integrity = restored.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        restored.close()
    assert value == "Жадный Мир"
    assert integrity == "ok"
    assert backup.filename.startswith("zhadny_mir_backup_")
    assert backup.filename.endswith(".db")


@pytest.mark.asyncio
async def test_sqlite_backup_can_be_kept_in_persistent_data_directory(tmp_path):
    source_path = tmp_path / "source.db"
    destination = tmp_path / "persistent" / "backups"
    with sqlite3.connect(source_path) as connection:
        connection.execute("CREATE TABLE example (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO example VALUES (42)")

    backup = await backup_service.create_sqlite_backup(
        source_path, destination_dir=destination
    )

    assert backup.stored_path == destination / backup.filename
    assert backup.stored_path.read_bytes() == backup.data
    with sqlite3.connect(backup.stored_path) as connection:
        assert connection.execute("SELECT value FROM example").fetchone()[0] == 42
