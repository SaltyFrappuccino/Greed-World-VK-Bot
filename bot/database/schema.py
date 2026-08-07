import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from bot.config import Settings, get_settings
from bot.database.models import Base

logger = logging.getLogger("zhadny_mir.database.schema")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def upgrade_and_verify_schema(settings: Settings | None = None) -> None:
    """Применить миграции к рабочей БД до запуска VK polling."""
    settings = settings or get_settings()
    settings.ensure_runtime_directories()
    database_url = settings.migration_database_url
    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False

    logger.info("database.migration.start data_dir=%s", settings.data_path)
    command.upgrade(config, "head")
    _verify_schema(database_url)
    logger.info("database.migration.done revision=head")


def _verify_schema(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        existing = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    missing = set(Base.metadata.tables) - existing
    if missing:
        raise RuntimeError(
            "Миграции завершились без обязательных таблиц: "
            + ", ".join(sorted(missing))
        )
