import json
from types import SimpleNamespace

import pytest

from bot.keyboards.admin_menu import (
    admin_cards_menu,
    admin_character_cards_menu,
    admin_character_add_menu,
    admin_character_edit_menu,
    admin_characters_menu,
    admin_menu,
    ai_collect_menu,
    ai_confirm_menu,
    back_to_admin,
    back_to_admin_cards,
    back_to_admin_characters,
    cancel_character_shakei_menu,
    card_add_mode_menu,
    card_owners_menu,
    card_rarity_menu,
    card_type_menu,
    contour_subtype_menu,
    contour_available_cards_menu,
    contour_components_actions_menu,
    contour_create_components_menu,
    contour_create_mode_menu,
    contour_current_component_menu,
    contour_delete_confirm_menu,
    contour_fields_menu,
    confirm_menu,
    selected_shakei_action_menu,
    skip_card_field_menu,
    special_card_limit_menu,
)
from bot.keyboards.main_menu import (
    back_to_menu,
    cancel,
    card_registry_detail_menu,
    card_registry_menu,
    character_registry_detail_menu,
    character_registry_menu,
    character_select_menu,
    character_contours_menu,
    contour_detail_menu,
    main_menu,
    profile_menu,
)


@pytest.mark.parametrize(
    "keyboard_json",
    [
        admin_menu(),
        admin_characters_menu(),
        admin_character_add_menu(),
        admin_cards_menu(),
        admin_character_cards_menu(1),
        admin_character_edit_menu(1),
        ai_collect_menu("admin_ai_character"),
        ai_confirm_menu("admin_ai_character"),
        back_to_admin(),
        back_to_admin_characters(),
        back_to_admin_cards(),
        card_add_mode_menu(),
        card_rarity_menu(),
        card_type_menu(),
        contour_subtype_menu(),
        contour_create_components_menu(
            [(1, "Покров", 1), (2, "Молния", 2)],
            selected_count=2,
            page=0,
            pages=1,
        ),
        contour_create_mode_menu(),
        contour_fields_menu(1),
        contour_available_cards_menu(
            [(1, "Покров", 1)],
            command="admin_contour_card_add_select",
            target_id=1,
            page=0,
            pages=1,
        ),
        contour_delete_confirm_menu(1),
        card_owners_menu(1),
        confirm_menu("delete", 1),
        selected_shakei_action_menu(1),
        cancel_character_shakei_menu(1),
        skip_card_field_menu("admin_card_description_skip"),
        special_card_limit_menu(),
        back_to_menu(),
        cancel(),
        main_menu(False),
        main_menu(True),
        card_registry_menu(
            [SimpleNamespace(id=index, name=f"Карта {index}") for index in range(1, 9)],
            1,
            3,
        ),
        card_registry_detail_menu(1, 1, is_admin=False),
        card_registry_detail_menu(1, 1, is_admin=True),
        character_registry_menu(
            [SimpleNamespace(id=index, name=f"Персонаж {index}") for index in range(1, 9)],
            1,
            3,
        ),
        character_registry_detail_menu(1, 1, is_admin=False),
        character_registry_detail_menu(1, 1, is_admin=True),
        profile_menu(1),
        profile_menu(1, is_admin=True),
        character_contours_menu(
            1,
            [(1, None), (2, None)],
            0,
            1,
            is_admin=True,
        ),
        contour_detail_menu(
            SimpleNamespace(
                id=1,
                character_id=1,
                card_capacity=2,
                components=[],
            ),
            is_admin=True,
        ),
        contour_components_actions_menu(
            SimpleNamespace(
                id=1,
                card_capacity=2,
                components=[],
            )
        ),
        contour_current_component_menu(
            SimpleNamespace(id=1, components=[]),
            "admin_contour_card_remove_confirm",
        ),
        character_select_menu(
            "profile_select",
            [SimpleNamespace(id=1, name="Ава"), SimpleNamespace(id=2, name="Хёдо")],
        ),
    ],
)
def test_dm_keyboard_is_persistent_and_fits_vk_limits(keyboard_json):
    keyboard = json.loads(keyboard_json)

    assert keyboard["inline"] is False
    assert keyboard["one_time"] is False
    assert len(keyboard["buttons"]) <= 10
    assert all(len(row) <= 5 for row in keyboard["buttons"])


def test_quick_mutation_buttons_are_visible_only_to_admin():
    player_card = _commands(card_registry_detail_menu(1, 0, is_admin=False))
    admin_card = _commands(card_registry_detail_menu(1, 0, is_admin=True))
    player_character = _commands(
        character_registry_detail_menu(1, 0, is_admin=False)
    )
    admin_character = _commands(
        character_registry_detail_menu(1, 0, is_admin=True)
    )
    player_own_profile = _commands(profile_menu(1))
    admin_own_profile = _commands(profile_menu(1, is_admin=True))

    assert "admin_card_edit_select" not in player_card
    assert "admin_card_delete_select" not in player_card
    assert {"admin_card_edit_select", "admin_card_delete_select"} <= admin_card
    assert "admin_character_edit_select" not in player_character
    assert "admin_character_delete_select" not in player_character
    assert {
        "admin_character_edit_select",
        "admin_character_delete_select",
        "admin_character_shakei",
    } <= admin_character
    assert "admin_character_edit_select" not in player_own_profile
    assert "admin_character_delete_select" not in player_own_profile
    assert {
        "admin_character_edit_select",
        "admin_character_delete_select",
        "admin_character_shakei",
    } <= admin_own_profile


def test_admin_menu_contains_database_backup():
    assert "admin_database_backup" in _commands(admin_menu())


def test_admin_menu_uses_entity_first_navigation():
    commands = _commands(admin_menu())

    assert {"admin_characters", "admin_cards", "admin_database_backup"} <= commands
    assert "admin_character_add" not in commands
    assert "admin_card_add" not in commands
    assert "admin_shakei" not in commands


def test_entity_menus_offer_add_or_select_existing():
    character_commands = _commands(admin_characters_menu())
    character_add_commands = _commands(admin_character_add_menu())
    card_commands = _commands(admin_cards_menu())

    assert character_commands >= {"admin_character_add_menu", "character_registry"}
    assert "admin_character_add" not in character_commands
    assert "admin_ai_character" not in character_commands
    assert {"admin_character_add", "admin_ai_character"} <= character_add_commands
    assert {"admin_card_add", "cards"} <= card_commands


def test_selected_character_actions_include_shakei_and_keep_context_on_cancel():
    actions = _commands(character_registry_detail_menu(42, 0, is_admin=True))
    shakei_actions = _commands(selected_shakei_action_menu(42))
    amount_cancel = _commands(cancel_character_shakei_menu(42))

    assert "admin_character_shakei" in actions
    assert {
        "admin_character_shakei_grant",
        "admin_character_shakei_deduct",
    } <= shakei_actions
    assert amount_cancel == {"admin_character_shakei"}


def _commands(keyboard_json):
    keyboard = json.loads(keyboard_json)
    return {
        button["action"]["payload"]["cmd"]
        for row in keyboard["buttons"]
        for button in row
    }
