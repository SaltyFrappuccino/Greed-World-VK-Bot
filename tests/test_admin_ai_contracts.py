from bot.services.admin_ai.contracts import parse_turn
from bot.services.admin_ai.orchestrator import _resolve_art_image_actions
from bot.services.admin_ai.values import _validate_action_arguments
from bot.services.errors import ValidationError

import pytest


def test_parse_turn_accepts_common_deepseek_json_variations():
    turn = parse_turn(
        """```json
        {
          "type": "read_tools",
          "answer": "Ищу персонажа",
          "tools": [
            {"name": "find_character", "arguments": "{\\"query\\": \\"Пикколо\\"}"}
          ],
          "actions": null,
          "warnings": null,
          "reasoning": "служебное поле будет отброшено"
        }
        ```"""
    )

    assert turn.kind == "read_tools"
    assert turn.message == "Ищу персонажа"
    assert turn.tools[0].arguments == {"query": "Пикколо"}
    assert turn.actions == []
    assert turn.warnings == []


def test_parse_turn_extracts_json_from_surrounding_text():
    turn = parse_turn(
        'Служебный префикс {"kind":"answer","message":"Готово"} хвост'
    )

    assert turn.kind == "answer"
    assert turn.message == "Готово"


def test_art_action_resolves_attached_image_index() -> None:
    actions = [
        {
            "name": "character_art_add",
            "arguments": {"character_id": 7, "image_index": 2, "caption": "Арт"},
        }
    ]
    _resolve_art_image_actions(
        actions,
        ["https://sun.userapi.com/one.jpg", "https://sun.userapi.com/two.jpg"],
    )
    arguments = actions[0]["arguments"]
    assert arguments["source_url"].endswith("two.jpg")
    assert "image_index" not in arguments


def test_new_character_art_resolves_inside_single_atomic_action() -> None:
    actions = [
        {
            "name": "character_create",
            "arguments": {
                "vk_id": 123,
                "name": "Пикколо",
                "arts": [{"image_index": 1, "make_primary": True}],
            },
        }
    ]

    _resolve_art_image_actions(actions, ["https://sun.userapi.com/piccolo.jpg"])

    art = actions[0]["arguments"]["arts"][0]
    assert art == {
        "source_url": "https://sun.userapi.com/piccolo.jpg",
        "make_primary": True,
    }
    _validate_action_arguments("character_create", actions[0]["arguments"])


def test_text_vk_name_cannot_be_used_as_internal_character_id() -> None:
    with pytest.raises(ValidationError, match="character_id.*целым числом"):
        _validate_action_arguments(
            "character_update",
            {"character_id": "idi_nahuy_dayn_tupoi", "fields": {"age": "31"}},
        )
