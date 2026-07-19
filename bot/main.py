from vkbottle.bot import Bot

from bot.config import get_settings
from bot.handlers.chat import labelers as chat_labelers
from bot.handlers.dm import control_labeler, fallback_labeler, labelers as dm_labelers
from bot.handlers.dm.admin import labelers as admin_labelers
from bot.logging_config import configure_logging
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.logging import LoggingMiddleware
from bot.states import state_dispenser
from bot.vkbottle_compat import ensure_runner_logger_compatibility


def create_bot() -> Bot:
    settings = get_settings()
    configure_logging(settings)
    ensure_runner_logger_compatibility()

    bot = Bot(token=settings.vk_community_token, state_dispenser=state_dispenser)
    bot.labeler.message_view.register_middleware(LoggingMiddleware)
    bot.labeler.message_view.register_middleware(AuthMiddleware)

    # Глобальные «Отмена» и «В меню» идут раньше обработчиков состояний.
    # Fallback всегда остаётся последним.
    for labeler in [
        control_labeler,
        *admin_labelers,
        *dm_labelers,
        *chat_labelers,
        fallback_labeler,
    ]:
        bot.labeler.load(labeler)
    return bot


def main() -> None:
    create_bot().run()


if __name__ == "__main__":
    main()
