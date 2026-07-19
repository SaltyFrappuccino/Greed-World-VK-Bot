from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Драйверы, которые надо подставить, чтобы синхронный DATABASE_URL из .env
# работал с async-движком SQLAlchemy. Ключ - схема из .env, значение - async-схема.
_ASYNC_DRIVERS = {
    "sqlite": "sqlite+aiosqlite",
    "postgresql": "postgresql+asyncpg",
    "postgres": "postgresql+asyncpg",
}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
def resolve_database_url(database_url: str) -> str:
    """Привязать относительный SQLite-файл к корню проекта, а не к cwd."""
    scheme, separator, path_text = database_url.partition(":///")
    if not separator or scheme not in {"sqlite", "sqlite+aiosqlite"}:
        return database_url
    if path_text == ":memory:":
        return database_url

    database_path = Path(path_text)
    if database_path.is_absolute():
        return database_url
    resolved = (_PROJECT_ROOT / database_path).resolve()
    return f"{scheme}:///{resolved.as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    vk_community_token: str
    vk_group_id: int
    vk_board_token: str | None = None
    vk_applications_topic_url: str | None = None

    admin_vk_ids: Annotated[list[int], NoDecode] = []

    database_url: str = "sqlite:///./zhadny_mir.db"

    character_art_storage_dir: str = "storage/character_art"
    character_art_max_file_bytes: int = 20 * 1024 * 1024
    character_art_max_total_bytes: int = 4 * 1024 * 1024 * 1024
    character_art_max_per_character: int = 50
    profile_card_storage_dir: str = "storage/profile_cards"
    profile_card_font_regular: str | None = None
    profile_card_font_bold: str | None = None

    log_level: str = "INFO"
    log_file: str = "logs/zhadny_mir.log"
    log_max_bytes: int = 5_242_880
    log_backup_count: int = 5

    dslab_api_key: str | None = None
    dslab_base_url: str = "https://api.dslab.tech/v1"
    dslab_model: str = "deepseek-v4-flash"
    dslab_vision_model: str = "gemini-2.5-flash-lite"
    dslab_max_tokens: int = 4000
    dslab_agent_max_tokens: int = 8000
    dslab_agent_timeout_seconds: float = 180.0

    @field_validator("admin_vk_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [chunk.strip() for chunk in value.split(",") if chunk.strip()]
        return value

    @property
    def async_database_url(self) -> str:
        """DATABASE_URL с async-драйвером.

        В .env лежит обычная синхронная строка (так её понимают alembic и
        внешние инструменты), а движок бота работает асинхронно.
        """
        database_url = resolve_database_url(self.database_url)
        scheme, _, rest = database_url.partition("://")
        if "+" in scheme:
            return database_url
        return f"{_ASYNC_DRIVERS.get(scheme, scheme)}://{rest}"

    @property
    def character_art_storage_path(self) -> Path:
        path = Path(self.character_art_storage_dir)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path.resolve()

    @property
    def profile_card_storage_path(self) -> Path:
        path = Path(self.profile_card_storage_dir)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path.resolve()

    def is_admin(self, vk_id: int) -> bool:
        return vk_id in self.admin_vk_ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
