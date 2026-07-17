import logging

from vkbottle import BaseMiddleware
from vkbottle.bot import Message

logger = logging.getLogger("zhadny_mir")


class LoggingMiddleware(BaseMiddleware[Message]):
    async def pre(self) -> None:
        source = "чат" if self.event.peer_id != self.event.from_id else "лс"
        logger.info(
            "[%s] от %s: %s",
            source,
            self.event.from_id,
            (self.event.text or "").replace("\n", " ")[:200],
        )
