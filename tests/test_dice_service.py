import random

import pytest

from bot.services import dice_service
from bot.services.errors import ValidationError


def test_default_and_custom_bounds():
    assert dice_service.parse_bounds("") == (1, 20)
    assert dice_service.parse_bounds("6") == (1, 6)
    assert dice_service.parse_bounds("20 1") == (20, 1)

    result = dice_service.roll(20, 1, rng=random.Random(1))
    assert result.low == 1
    assert result.high == 20
    assert 1 <= result.value <= 20


def test_more_than_two_bounds_are_rejected():
    with pytest.raises(ValidationError, match="не больше двух"):
        dice_service.parse_bounds("1 20 30")
