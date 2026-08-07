import sqlite3

from bot.config import Settings
from bot.database.schema import upgrade_and_verify_schema


def test_startup_migrations_create_ai_assistant_tables(tmp_path):
    database_path = tmp_path / "data" / "zhadny_mir.db"
    settings = Settings(
        _env_file=None,
        vk_community_token="test",
        vk_group_id=1,
        data_dir=str(tmp_path / "data"),
        database_url=f"sqlite:///{database_path.as_posix()}",
        log_file="",
    )

    upgrade_and_verify_schema(settings)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]

    assert "admin_ai_sessions" in tables
    assert "admin_ai_messages" in tables
    assert "admin_ai_plans" in tables
    assert revision == "0012_book_slots_and_trophies"


def test_startup_migrations_are_idempotent(tmp_path):
    database_path = tmp_path / "data" / "zhadny_mir.db"
    settings = Settings(
        _env_file=None,
        vk_community_token="test",
        vk_group_id=1,
        data_dir=str(tmp_path / "data"),
        database_url=f"sqlite:///{database_path.as_posix()}",
        log_file="",
    )

    upgrade_and_verify_schema(settings)
    upgrade_and_verify_schema(settings)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM alembic_version"
        ).fetchone()[0] == 1
