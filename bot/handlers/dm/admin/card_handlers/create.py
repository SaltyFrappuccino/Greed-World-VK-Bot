"""Compatibility facade for card creation workflows."""

from bot.handlers.dm.admin.card_handlers.setup import *  # noqa: F403
from bot.handlers.dm.admin.card_handlers.wizard import *  # noqa: F403
from bot.handlers.dm.admin.card_handlers.wizard import (
    _after_description,
    _after_spell_activation,
    _create_spell_card,
    _create_wizard_card,
)
