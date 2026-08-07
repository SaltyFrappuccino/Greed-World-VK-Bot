from pathlib import Path

from bot.config import Settings


def test_admin_ids_are_read_from_comma_separated_env(monkeypatch):
    monkeypatch.setenv("VK_COMMUNITY_TOKEN", "test")
    monkeypatch.setenv("VK_GROUP_ID", "1")
    monkeypatch.setenv("ADMIN_VK_IDS", "111111, 222222")

    settings = Settings(_env_file=None)

    assert settings.admin_vk_ids == [111111, 222222]
    assert settings.is_admin(222222)


def test_relative_sqlite_path_is_resolved_from_project_root():
    settings = Settings(
        _env_file=None,
        vk_community_token="test",
        vk_group_id=1,
        database_url="sqlite:///./zhadny_mir.db",
    )

    path = settings.async_database_url.removeprefix("sqlite+aiosqlite:///")
    assert Path(path).is_absolute()
    assert Path(path).name == "zhadny_mir.db"


def test_data_dir_rebases_all_relative_persistent_paths(tmp_path):
    data_dir = tmp_path / "persistent"
    settings = Settings(
        _env_file=None,
        vk_community_token="test",
        vk_group_id=1,
        data_dir=str(data_dir),
        database_url="sqlite:///./zhadny_mir.db",
        character_art_storage_dir="storage/character_art",
        profile_card_storage_dir="storage/profile_cards",
        log_file="logs/bot.log",
    )

    database_path = Path(
        settings.async_database_url.removeprefix("sqlite+aiosqlite:///")
    )
    assert database_path == data_dir / "zhadny_mir.db"
    assert settings.character_art_storage_path == data_dir / "storage/character_art"
    assert settings.profile_card_storage_path == data_dir / "storage/profile_cards"
    assert settings.backup_storage_path == data_dir / "backups"
    assert settings.log_path == data_dir / "logs/bot.log"

    settings.ensure_runtime_directories()

    assert data_dir.is_dir()
    assert settings.character_art_storage_path.is_dir()
    assert settings.profile_card_storage_path.is_dir()
    assert settings.backup_storage_path.is_dir()
    assert settings.log_path.parent.is_dir()


def test_absolute_persistent_paths_are_not_rebased(tmp_path):
    database_path = tmp_path / "database.db"
    art_path = tmp_path / "arts"
    settings = Settings(
        _env_file=None,
        vk_community_token="test",
        vk_group_id=1,
        data_dir=str(tmp_path / "other"),
        database_url=f"sqlite:///{database_path.as_posix()}",
        character_art_storage_dir=str(art_path),
    )

    assert Path(
        settings.async_database_url.removeprefix("sqlite+aiosqlite:///")
    ) == database_path
    assert settings.character_art_storage_path == art_path


def test_legacy_relative_data_is_moved_to_data_dir_once(tmp_path, monkeypatch):
    project_root = tmp_path / "app"
    data_dir = tmp_path / "data"
    (project_root / "storage/character_art/characters/1").mkdir(parents=True)
    (project_root / "storage/character_art/characters/1/art.jpg").write_bytes(b"art")
    (project_root / "zhadny_mir.db").write_bytes(b"database")
    monkeypatch.setattr("bot.config._PROJECT_ROOT", project_root)
    settings = Settings(
        _env_file=None,
        vk_community_token="test",
        vk_group_id=1,
        data_dir=str(data_dir),
        database_url="sqlite:///./zhadny_mir.db",
    )

    settings.ensure_runtime_directories()

    assert (data_dir / "zhadny_mir.db").read_bytes() == b"database"
    assert (
        data_dir / "storage/character_art/characters/1/art.jpg"
    ).read_bytes() == b"art"

    (data_dir / "zhadny_mir.db").write_bytes(b"persistent")
    settings.ensure_runtime_directories()
    assert (data_dir / "zhadny_mir.db").read_bytes() == b"persistent"


def test_dslab_defaults_use_requested_openai_compatible_endpoint():
    settings = Settings(
        _env_file=None,
        vk_community_token="test",
        vk_group_id=1,
    )

    assert settings.dslab_base_url == "https://api.dslab.tech/v1"
    assert settings.dslab_model == "deepseek-v4-flash"
    assert settings.dslab_vision_model == "gemini-2.5-flash-lite"
