"""Compatibility facade for the decomposed admin keyboards."""

from bot.keyboards.admin.cards import (
    ai_collect_menu,
    ai_confirm_menu,
    back_to_admin,
    back_to_admin_cards,
    back_to_admin_characters,
    card_add_mode_menu,
    card_owners_menu,
    card_rarity_menu,
    card_type_menu,
    confirm_menu,
    contour_subtype_menu,
    skip_card_field_menu,
    special_card_limit_menu,
)
from bot.keyboards.admin.characters import (
    admin_character_cards_menu,
    admin_character_edit_menu,
)
from bot.keyboards.admin.contours import (
    contour_ai_collect_menu,
    contour_ai_confirm_menu,
    contour_available_cards_menu,
    contour_components_actions_menu,
    contour_create_components_menu,
    contour_create_mode_menu,
    contour_current_component_menu,
    contour_delete_confirm_menu,
    contour_fields_menu,
)
from bot.keyboards.admin.root import (
    admin_ai_assistant_menu,
    admin_ai_destructive_menu,
    admin_ai_plan_menu,
    admin_cards_menu,
    admin_character_add_menu,
    admin_characters_menu,
    admin_menu,
    cancel_character_shakei_menu,
    selected_shakei_action_menu,
)

__all__ = [name for name in globals() if not name.startswith("_")]
