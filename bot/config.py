import shutil
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ASYNC_DRIVERS = {
    "sqlite": "sqlite+aiosqlite",
    "postgresql": "postgresql+asyncpg",
    "postgres": "postgresql+asyncpg",
}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_data_dir(data_dir: str | Path | None = None) -> Path:
    """Корень постоянных данных: DATA_DIR на хостинге, проект локально."""
    if data_dir is None or not str(data_dir).strip():
        return _PROJECT_ROOT
    path = Path(data_dir).expanduser()
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path.resolve()


def resolve_data_path(path_value: str | Path, data_dir: str | Path | None = None) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = resolve_data_dir(data_dir) / path
    return path.resolve()


def resolve_database_url(
    database_url: str, data_dir: str | Path | None = None
) -> str:
    """Привязать относительный SQLite-файл к каталогу постоянных данных."""
    scheme, separator, path_text = database_url.partition(":///")
    if not separator or scheme not in {"sqlite", "sqlite+aiosqlite"}:
        return database_url
    if path_text == ":memory:":
        return database_url

    database_path = Path(path_text)
    if database_path.is_absolute():
        return database_url
    resolved = resolve_data_path(database_path, data_dir)
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

    data_dir: str | None = None
    database_url: str = "sqlite:///./zhadny_mir.db"
    backup_storage_dir: str = "backups"

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
    dslab_agent_max_retries: int = 2

    @field_validator("admin_vk_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value: object) -> object:
        if isinstance(value, str):
            result: list[int] = []
            for chunk in (chunk.strip() for chunk in value.split(",") if chunk.strip()):
                try:
                    result.append(int(chunk))
                except Exception:
                    # ignore bad values but keep parsing
                    continue
            return result
        return value

    @property
    def async_database_url(self) -> str:
        """DATABASE_URL с async-драйвером.

        В .env лежит обычная синхронная строка (так её понимают alembic и
        внешние инструменты), а движок бота работает асинхронно.
        """
        database_url = resolve_database_url(self.database_url, self.data_dir)
        scheme, _, rest = database_url.partition("://")
        if "+" in scheme:
            return database_url
        return f"{_ASYNC_DRIVERS.get(scheme, scheme)}://{rest}"

    @property
    def character_art_storage_path(self) -> Path:
        return resolve_data_path(self.character_art_storage_dir, self.data_dir)

    @property
    def profile_card_storage_path(self) -> Path:
        return resolve_data_path(self.profile_card_storage_dir, self.data_dir)

    @property
    def backup_storage_path(self) -> Path:
        return resolve_data_path(self.backup_storage_dir, self.data_dir)

    @property
    def data_path(self) -> Path:
        return resolve_data_dir(self.data_dir)

    @property
    def log_path(self) -> Path | None:
        if not self.log_file.strip():
            return None
        return resolve_data_path(self.log_file, self.data_dir)

    def ensure_runtime_directories(self) -> None:
        """Подготовить каталоги, которые должны переживать перезапуск контейнера."""
        self.migrate_legacy_runtime_data()
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.character_art_storage_path.mkdir(parents=True, exist_ok=True)
        self.profile_card_storage_path.mkdir(parents=True, exist_ok=True)
        self.backup_storage_path.mkdir(parents=True, exist_ok=True)
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

        database_url = resolve_database_url(self.database_url, self.data_dir)
        scheme, separator, path_text = database_url.partition(":///")
        if (
            separator
            and scheme in {"sqlite", "sqlite+aiosqlite"}
            and path_text != ":memory:"
        ):
            Path(path_text).parent.mkdir(parents=True, exist_ok=True)

    def migrate_legacy_runtime_data(self) -> None:
        """Один раз скопировать старые относительные файлы из корня приложения."""
        if self.data_dir is None or not self.data_dir.strip():
            return

        scheme, separator, path_text = self.database_url.partition(":///")
        if separator and scheme in {"sqlite", "sqlite+aiosqlite"}:
            database_path = Path(path_text)
            if path_text != ":memory:" and not database_path.is_absolute():
                self._copy_legacy_file(database_path)

        self._copy_legacy_directory(Path(self.character_art_storage_dir))
        self._copy_legacy_directory(Path(self.profile_card_storage_dir))
        self._copy_legacy_directory(Path(self.backup_storage_dir))
        if self.log_file.strip():
            self._copy_legacy_file(Path(self.log_file))

    def _copy_legacy_file(self, relative_path: Path) -> None:
        if relative_path.is_absolute():
            return
        source = (_PROJECT_ROOT / relative_path).resolve()
        target = (self.data_path / relative_path).resolve()
        if source == target or not source.is_file() or target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def _copy_legacy_directory(self, relative_path: Path) -> None:
        if relative_path.is_absolute():
            return
        source = (_PROJECT_ROOT / relative_path).resolve()
        target = (self.data_path / relative_path).resolve()
        if source == target or not source.is_dir() or target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)

    def is_admin(self, vk_id: int) -> bool:
        return vk_id in self.admin_vk_ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
