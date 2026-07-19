from types import SimpleNamespace

import pytest

from bot.handlers.chat.card_usage import _parse_usage
from bot.services.errors import ValidationError


class _Message:
    def __init__(self, reply_vk_id: int | None = None, from_id: int = 999) -> None:
        self.from_id = from_id
        self.reply_message = (
            SimpleNamespace(from_id=reply_vk_id) if reply_vk_id is not None else None
        )


def test_usage_parser_supports_character_quantity_and_mention() -> None:
    result = _parse_usage(
        _Message(), "#12 Перенос x2 [id123|Слава]"
    )

    assert result == (12, "Перенос", 2, 123)


def test_usage_parser_defaults_character_and_quantity_and_accepts_reply() -> None:
    result = _parse_usage(_Message(reply_vk_id=456), "Яблоко")

    assert result == (None, "Яблоко", 1, 456)


def test_usage_parser_requires_scene_partner() -> None:
    with pytest.raises(ValidationError, match="Упомяните соигрока"):
        _parse_usage(_Message(), "Перенос")


def test_usage_parser_rejects_sender_as_scene_partner() -> None:
    with pytest.raises(ValidationError, match="соигрока"):
        _parse_usage(_Message(from_id=123), "Перенос [id123|Я]")
