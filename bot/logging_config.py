import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from bot.config import Settings


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(settings: Settings) -> None:
    """Configure console logging and a persistent rotating UTF-8 log."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    root = logging.getLogger()
    root.setLevel(level)

    vkbottle_logger = logging.getLogger("vkbottle")
    vkbottle_logger.handlers.clear()
    vkbottle_logger.propagate = True

    if not any(getattr(handler, "_zhadny_console", False) for handler in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console._zhadny_console = True  # type: ignore[attr-defined]
        root.addHandler(console)

    if not settings.log_file.strip():
        return
    log_path = settings.log_path
    if log_path is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = log_path.resolve()
    if any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename).resolve() == resolved
        for handler in root.handlers
    ):
        return
    file_handler = RotatingFileHandler(
        resolved,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
