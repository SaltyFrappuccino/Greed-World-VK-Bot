def parse_labeled_template(text: str, labels: dict[str, str]) -> dict[str, str]:
    """Разобрать «Подпись: значение» с поддержкой многострочных значений."""
    normalized = {label.casefold(): field for label, field in labels.items()}
    result: dict[str, str] = {}
    current_field: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_field and result.get(current_field):
                result[current_field] += "\n"
            continue

        label, separator, value = line.partition(":")
        field = normalized.get(label.strip().casefold()) if separator else None
        if field is not None:
            current_field = field
            result[field] = value.strip()
            continue

        # Пояснение бота перед первой подписью тоже можно скопировать вместе
        # с шаблоном — оно не должно мешать разбору.
        if current_field is None:
            continue
        result[current_field] = (result[current_field] + "\n" + line).strip()

    return result
