from bot.services.errors import ValidationError

CONTOUR_TEMPLATE = """Заполните шаблон и пришлите одним сообщением. Состав уже выбран кнопками и сюда не включается.

Название:
Внешний вид:
Основной эффект:
Дополнительные возможности:
Условия активации:
Продолжительность:
Проводимость:
Влияние на Перегрузку:"""

FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "Название"),
    ("appearance", "Внешний вид"),
    ("primary_effect", "Основной эффект"),
    ("additional_capabilities", "Дополнительные возможности"),
    ("activation_conditions", "Условия активации"),
    ("duration", "Продолжительность"),
    ("conductivity", "Проводимость"),
    ("overload_impact", "Влияние на Перегрузку"),
)


def parse_contour_template(text: str) -> dict[str, str]:
    labels = {label.casefold(): field for field, label in FIELDS}
    result = {field: "" for field, _ in FIELDS}
    current: str | None = None
    chunks: list[str] = []

    def save() -> None:
        if current is not None:
            result[current] = "\n".join(chunks).strip()

    for line in text.splitlines():
        label_text, separator, value = line.partition(":")
        field = labels.get(label_text.strip().casefold()) if separator else None
        if field is not None:
            save()
            current = field
            chunks = [value.strip()] if value.strip() else []
        elif current is not None:
            chunks.append(line.rstrip())
    save()

    if not result["name"]:
        raise ValidationError("В шаблоне не заполнено поле «Название».")
    return result
