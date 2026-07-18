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


def test_dslab_defaults_use_requested_openai_compatible_endpoint():
    settings = Settings(
        _env_file=None,
        vk_community_token="test",
        vk_group_id=1,
    )

    assert settings.dslab_base_url == "https://api.dslab.tech/v1"
    assert settings.dslab_model == "deepseek-v4-flash"
    assert settings.dslab_vision_model == "gemini-2.5-flash-lite"
