"""Compatibility facade for the decomposed direct-message keyboards."""

from bot.keyboards.main.cards import (
    card_registry_categories,
    card_registry_detail_menu,
    card_registry_menu,
)
from bot.keyboards.main.arts import (
    character_art_delete_confirm_menu,
    character_art_detail_menu,
    character_arts_menu,
)
from bot.keyboards.main.characters import (
    character_registry_detail_menu,
    character_registry_menu,
)
from bot.keyboards.main.contours import character_contours_menu, contour_detail_menu
from bot.keyboards.main.root import (
    back_to_menu,
    cancel,
    character_select_menu,
    main_menu,
    profile_menu,
)

__all__ = [name for name in globals() if not name.startswith("_")]
