"""Card admin router assembled from focused workflow modules."""

from bot.handlers.dm.admin.card_handlers.create import *  # noqa: F403
from bot.handlers.dm.admin.card_handlers.create import _after_description
from bot.handlers.dm.admin.card_handlers.edit import *  # noqa: F403
from bot.handlers.dm.admin.card_handlers.routing import labeler
