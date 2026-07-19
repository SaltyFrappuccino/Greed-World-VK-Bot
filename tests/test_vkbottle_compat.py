from bot.vkbottle_compat import ensure_runner_logger_compatibility


class _StyleLoggerWithoutOpt:
    def __init__(self) -> None:
        self.errors: list[tuple[str, dict[str, object]]] = []

    def error(self, message: str, *args: object, **kwargs: object) -> None:
        self.errors.append((message, kwargs))


def test_runner_logger_compatibility_preserves_original_exception(monkeypatch) -> None:
    from vkbottle.tools import _runner

    logger = _StyleLoggerWithoutOpt()
    monkeypatch.setattr(_runner, "logger", logger)
    original = RuntimeError("первичная ошибка polling")

    ensure_runner_logger_compatibility()
    _runner.logger.opt(exception=original).error("Unhandled exception in task")

    assert len(logger.errors) == 1
    message, kwargs = logger.errors[0]
    assert message == "Unhandled exception in task"
    assert kwargs["exc_info"][:2] == (RuntimeError, original)


def test_runner_logger_compatibility_is_idempotent(monkeypatch) -> None:
    from vkbottle.tools import _runner

    monkeypatch.setattr(_runner, "logger", _StyleLoggerWithoutOpt())
    ensure_runner_logger_compatibility()
    compatible_logger = _runner.logger

    ensure_runner_logger_compatibility()

    assert _runner.logger is compatible_logger
