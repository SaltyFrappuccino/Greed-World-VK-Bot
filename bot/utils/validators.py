import re

from bot.database.models import Rarity
from bot.services.errors import ValidationError

_MENTION_RE = re.compile(r"\[(?:id|club)(\d+)\|[^\]]*\]")
_VK_ID_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?vk\.(?:com|ru)/id(\d+)/?", re.IGNORECASE)
_VK_PROFILE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?vk\.(?:com|ru)/([A-Za-z0-9_.]+)/?",
    re.IGNORECASE,
)


def parse_int(value: str, *, field: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        raise ValidationError(f"{field}: нужно целое число, а пришло «{value.strip()}».") from None


def parse_positive_int(value: str, *, field: str) -> int:
    number = parse_int(value, field=field)
    if number <= 0:
        raise ValidationError(f"{field}: число должно быть больше нуля.")
    return number


def parse_rarity(value: str) -> Rarity:
    key = value.strip().upper()
    try:
        return Rarity[key]
    except KeyError:
        allowed = ", ".join(rarity.value for rarity in Rarity)
        raise ValidationError(f"Неизвестная редкость «{value.strip()}». Допустимы: {allowed}.") from None


def parse_optional_limit(value: str) -> int | None:
    """«-», «нет», «0» - лимита нет; иначе положительное число."""
    key = value.strip().lower()
    if key in {"-", "нет", "без", "0", ""}:
        return None
    return parse_positive_int(value, field="Лимит преобразований")


def parse_optional_slot_number(value: str) -> int | None:
    """Номер Особого слота 0–99 или отсутствие номера."""
    key = value.strip().lower()
    if key in {"-", "нет", "без", ""}:
        return None
    number = parse_int(value, field="Номер Особого слота")
    if not 0 <= number <= 99:
        raise ValidationError("Номер Особого слота должен быть от 0 до 99.")
    return number


def extract_vk_id(text: str) -> int | None:
    """Достать vk_id из упоминания вида [id123|Имя]."""
    match = _MENTION_RE.search(text)
    return int(match.group(1)) if match else None


def strip_mentions(text: str) -> str:
    return _MENTION_RE.sub("", text).strip()


def parse_vk_id(text: str) -> int:
    """VK ID из числа, упоминания [id...|...] или ссылки vk.com/id...."""
    mentioned = extract_vk_id(text)
    if mentioned is not None:
        return mentioned
    value = text.strip()
    if value.isdigit():
        return int(value)
    match = _VK_ID_URL_RE.fullmatch(value)
    if match:
        return int(match.group(1))
    raise ValidationError(
        "Пришлите числовой VK ID, упоминание пользователя или ссылку вида vk.com/id123."
    )


def parse_vk_reference(text: str) -> int | str:
    """Числовой ID либо короткое имя, которое надо разрешить через VK API."""
    try:
        return parse_vk_id(text)
    except ValidationError:
        pass

    value = text.strip()
    match = _VK_PROFILE_URL_RE.fullmatch(value)
    screen_name = match.group(1) if match else value.removeprefix("@").strip()
    if re.fullmatch(r"[A-Za-z0-9_.]+", screen_name):
        return screen_name
    raise ValidationError(
        "Пришлите VK ID, упоминание или ссылку на профиль, например vk.ru/username."
    )


def extract_vk_profile_urls(text: str) -> list[str]:
    """Найти ссылки на профили VK внутри произвольного пользовательского текста."""
    result: list[str] = []
    for match in _VK_PROFILE_URL_RE.finditer(text):
        url = match.group(0).rstrip("/.,;:!?)\"]}")
        if url not in result:
            result.append(url)
    return result
