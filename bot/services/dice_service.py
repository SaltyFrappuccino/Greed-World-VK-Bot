import random
from dataclasses import dataclass

from bot.services.errors import ValidationError

DEFAULT_MIN = 1
DEFAULT_MAX = 20
MAX_BOUND = 1_000_000


@dataclass(frozen=True)
class DiceRoll:
    low: int
    high: int
    value: int


def roll(low: int = DEFAULT_MIN, high: int = DEFAULT_MAX, *, rng: random.Random | None = None) -> DiceRoll:
    """Бросок кубика в диапазоне [low, high] - для тупиковых сцен."""
    if low > high:
        low, high = high, low
    if abs(low) > MAX_BOUND or abs(high) > MAX_BOUND:
        raise ValidationError(f"Границы кубика должны быть в пределах ±{MAX_BOUND}.")

    generator = rng or random
    return DiceRoll(low=low, high=high, value=generator.randint(low, high))


def parse_bounds(args: str) -> tuple[int, int]:
    """Разбор аргументов «?!кубик», «?!кубик 6», «?!кубик 1 20»."""
    parts = args.split()
    if not parts:
        return DEFAULT_MIN, DEFAULT_MAX
    if len(parts) > 2:
        raise ValidationError(
            "Укажите не больше двух границ: «?!кубик», «?!кубик 6» или «?!кубик 1 20»."
        )

    try:
        numbers = [int(part) for part in parts[:2]]
    except ValueError:
        raise ValidationError(
            "Кубик понимает только числа: «?!кубик», «?!кубик 6» или «?!кубик 1 20»."
        ) from None

    if len(numbers) == 1:
        return DEFAULT_MIN, numbers[0]
    return numbers[0], numbers[1]
