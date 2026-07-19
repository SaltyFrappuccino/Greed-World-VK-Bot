from vkbottle.bot import BotLabeler
from vkbottle.dispatch.rules.base import PeerRule

from bot.middlewares.auth import AdminRule


labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True

