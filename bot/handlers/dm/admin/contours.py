"""Contour admin router assembled from focused workflow modules."""

from bot.handlers.dm.admin.contour_handlers.create import *  # noqa: F403
from bot.handlers.dm.admin.contour_handlers.edit import *  # noqa: F403
from bot.handlers.dm.admin.contour_handlers.input import *  # noqa: F403
from bot.handlers.dm.admin.contour_handlers.routing import labeler
from bot.handlers.dm.admin.contour_handlers.support import _require_state
