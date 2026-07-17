from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from vkbottle.dispatch.rules import ABCRule

from bot.config import get_settings


class AuthMiddleware(BaseMiddleware[Message]):
    """Прокидывает роль отправителя в хендлеры - те сами права не проверяют."""

    async def pre(self) -> None:
        settings = get_settings()
        self.send({"is_admin": settings.is_admin(self.event.from_id)})


class AdminRule(ABCRule[Message]):
    """Пропускает только админов из ADMIN_VK_IDS.

    Вешается на auto_rules админского лейблера, так что закрывает все
    админские хендлеры разом - вручную в каждом ничего проверять не надо.
    """

    async def check(self, event: Message) -> bool:
        return get_settings().is_admin(event.from_id)


class NotAdminRule(ABCRule[Message]):
    """Пропускает fallback отказа только для обычных пользователей."""

    async def check(self, event: Message) -> bool:
        return not get_settings().is_admin(event.from_id)
