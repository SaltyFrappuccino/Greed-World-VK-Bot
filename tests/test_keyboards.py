import json
from types import SimpleNamespace

import pytest

from bot.keyboards.admin_menu import (
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
    character_select_menu,
    main_menu,
    profile_edit_menu,
    profile_menu,
)


@pytest.mark.parametrize(
    "keyboard_json",
    [
        admin_menu(),
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
        profile_edit_menu(1, False),
        profile_edit_menu(1, True),
        profile_menu(1),
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
