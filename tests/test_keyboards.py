import json
from types import SimpleNamespace

import pytest

from bot.keyboards.admin_menu import (
    admin_character_edit_menu,
    admin_menu,
    ai_collect_menu,
    ai_confirm_menu,
    back_to_admin,
    card_type_menu,
    confirm_menu,
    shakei_action_menu,
)
from bot.keyboards.main_menu import (
    back_to_menu,
    cancel,
    card_registry_detail_menu,
    card_registry_menu,
    character_registry_detail_menu,
    character_registry_menu,
    character_select_menu,
    main_menu,
    profile_menu,
)


@pytest.mark.parametrize(
    "keyboard_json",
    [
        admin_menu(),
        admin_character_edit_menu(1),
        ai_collect_menu("admin_ai_character"),
        ai_confirm_menu("admin_ai_character"),
        back_to_admin(),
        card_type_menu(),
        confirm_menu("delete", 1),
        shakei_action_menu(),
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
    } <= admin_character
    assert "admin_character_edit_select" not in player_own_profile
    assert "admin_character_delete_select" not in player_own_profile
    assert {
        "admin_character_edit_select",
        "admin_character_delete_select",
    } <= admin_own_profile


def test_admin_menu_contains_database_backup():
    assert "admin_database_backup" in _commands(admin_menu())


def _commands(keyboard_json):
    keyboard = json.loads(keyboard_json)
    return {
        button["action"]["payload"]["cmd"]
        for row in keyboard["buttons"]
        for button in row
    }
