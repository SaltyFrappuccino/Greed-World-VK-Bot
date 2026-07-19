from __future__ import annotations

from typing import Any


class _ExceptionBoundLogger:
    def __init__(self, logger: Any, exception: BaseException | None) -> None:
        self._logger = logger
        self._exception = exception

    def error(self, message: str, *args: object, **kwargs: object) -> None:
        if self._exception is not None:
            kwargs.setdefault(
                "exc_info",
                (
                    type(self._exception),
                    self._exception,
                    self._exception.__traceback__,
                ),
            )
        self._logger.error(message, *args, **kwargs)


class _RunnerLoggerCompat:
    """Добавить loguru-подобный opt стандартному логгеру vkbottle 4.10."""

    def __init__(self, logger: Any) -> None:
        self._logger = logger

    def opt(
        self, *, exception: BaseException | None = None, **_: object
    ) -> _ExceptionBoundLogger:
        return _ExceptionBoundLogger(self._logger, exception)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._logger, name)


def ensure_runner_logger_compatibility() -> None:
    """Не дать vkbottle скрыть исходное исключение отсутствующим logger.opt."""
    from vkbottle.tools import _runner

    if not hasattr(_runner.logger, "opt"):
        _runner.logger = _RunnerLoggerCompat(_runner.logger)
