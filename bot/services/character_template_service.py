from bot.services import character_service
from bot.services.errors import ValidationError
from bot.utils.templates import parse_labeled_template
from bot.utils.validators import parse_positive_int, parse_rarity

CHARACTER_TEMPLATE = """Скопируйте шаблон, заполните значения после двоеточий и пришлите одним сообщением.
Общий рейтинг нового персонажа будет H, баланс Шакеев — 0, Контуры — пустые.

Имя:
Возраст:
Пол:
Внешность:
Характер:
Биография:
Стрессоустойчивость:
Речевой аппарат:
Чуйка:
Хребет:
Воля:
Нюх:
Навыки:
Дополнительно:"""

_LABELS = {
    "Имя": "name",
    "Возраст": "age",
    "Пол": "gender",
    "Внешность": "appearance",
    "Характер": "personality",
    "Биография": "biography",
    "Стрессоустойчивость": "stress_resistance",
    "Речевой аппарат": "speech",
    "Чуйка": "intuition",
    "Хребет": "spine",
    "Воля": "will",
    "Нюх": "scent",
    "Навыки": "skills",
    "Дополнительно": "additional",
}


def parse_character_template(text: str) -> dict[str, object]:
    values = parse_labeled_template(text, _LABELS)
    required = {
        "name",
        "stress_resistance",
        "speech",
        "intuition",
        "spine",
        "will",
        "scent",
    }
    missing = [field for field in required if not values.get(field, "").strip()]
    if missing:
        raise ValidationError("Заполните имя и все шесть статов.")

    result: dict[str, object] = {
        "name": values["name"].strip(),
        "gender": _optional_text(values.get("gender", "")),
        "appearance": _optional_text(values.get("appearance", "")),
        "personality": _optional_text(values.get("personality", "")),
        "biography": _optional_text(values.get("biography", "")),
        "skills": _optional_text(values.get("skills", "")),
        "additional": _optional_text(values.get("additional", "")),
        "overall_rating": parse_rarity("H"),
        "is_approved": True,
    }
    age = values.get("age", "").strip()
    result["age"] = None if age in {"", "-"} else parse_positive_int(age, field="Возраст")

    for field in character_service.STAT_FIELDS:
        value = parse_positive_int(values[field], field=character_service.STAT_FIELDS[field])
        result[field] = character_service.validate_stat_value(value)
    return result


def _optional_text(value: str) -> str:
    value = value.strip()
    return "" if value == "-" else value
