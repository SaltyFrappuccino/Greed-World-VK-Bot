from copy import deepcopy

from bot.services.errors import ValidationError


_STAT_ALIASES = {
    "stress_resistance": "stress_resistance",
    "stress": "stress_resistance",
    "стрессоустойчивость": "stress_resistance",
    "speech": "speech",
    "speech_apparatus": "speech",
    "речевой аппарат": "speech",
    "intuition": "intuition",
    "чуйка": "intuition",
    "spine": "spine",
    "хребет": "spine",
    "will": "will",
    "воля": "will",
    "scent": "scent",
    "нюх": "scent",
}


def normalize_action_arguments(
    name: str, arguments: dict[str, object]
) -> dict[str, object]:
    """Перевести частые человекочитаемые поля LLM в строгий контракт."""
    result = deepcopy(arguments)
    if name in {"character_create", "character_import_discussion"}:
        _normalize_character_create(result)
    return result


def _normalize_character_create(arguments: dict[str, object]) -> None:
    raw_fields = arguments.get("fields", {})
    if raw_fields is None:
        raw_fields = {}
    if not isinstance(raw_fields, dict):
        raise ValidationError("Поле fields новой анкеты должно быть объектом.")
    fields = dict(raw_fields)

    # Flash-модели нередко выносят секции анкеты рядом с fields.
    for alias in ("character", "stats", "weakness", "rating", "shakei", "contours"):
        if alias in arguments:
            fields.setdefault(alias, arguments.pop(alias))

    _move_alias(fields, "character", "personality")
    _move_alias(fields, "характер", "personality")
    _move_alias(fields, "rating", "overall_rating")
    _move_alias(fields, "рейтинг", "overall_rating")
    _merge_weakness(fields)
    _flatten_stats(fields)
    _discard_starting_defaults(fields)
    _normalize_scalars(fields)
    # Анкеты создаёт только администратор, отдельная модерация не нужна.
    fields["is_approved"] = True
    arguments["fields"] = fields


def _move_alias(fields: dict[str, object], alias: str, canonical: str) -> None:
    if alias not in fields:
        return
    value = fields.pop(alias)
    fields.setdefault(canonical, value)


def _merge_weakness(fields: dict[str, object]) -> None:
    weakness = fields.pop("weakness", fields.pop("слабость", ""))
    if not str(weakness).strip():
        return
    line = f"Слабость: {str(weakness).strip()}"
    additional = str(fields.get("additional", "")).strip()
    fields["additional"] = f"{additional}\n\n{line}".strip()


def _flatten_stats(fields: dict[str, object]) -> None:
    stats = fields.pop("stats", fields.pop("статы", None))
    if stats is None:
        return
    if not isinstance(stats, dict):
        raise ValidationError("Блок stats новой анкеты должен быть объектом.")
    unknown: list[str] = []
    for raw_name, value in stats.items():
        key = str(raw_name).strip().casefold().replace("ё", "е")
        canonical = _STAT_ALIASES.get(key)
        if canonical is None:
            unknown.append(str(raw_name))
            continue
        fields.setdefault(canonical, value)
    if unknown:
        raise ValidationError(
            "Неизвестные статы новой анкеты: " + ", ".join(sorted(unknown)) + "."
        )


def _discard_starting_defaults(fields: dict[str, object]) -> None:
    shakei = fields.pop("shakei", fields.pop("шакеи", 0))
    try:
        shakei_value = int(shakei or 0)
    except (TypeError, ValueError) as error:
        raise ValidationError("Стартовые Шакеи должны быть числом 0.") from error
    if shakei_value != 0:
        raise ValidationError(
            "Новая анкета создаётся с 0 Шакеев; дальнейшие изменения журналируются отдельно."
        )
    # Текстовый шаблон пустых Контуров не является записью Контура в БД.
    fields.pop("contours", None)
    fields.pop("контуры", None)


def _normalize_scalars(fields: dict[str, object]) -> None:
    if "age" in fields and fields["age"] not in (None, ""):
        try:
            fields["age"] = int(fields["age"])
        except (TypeError, ValueError) as error:
            raise ValidationError("Возраст новой анкеты должен быть целым числом.") from error
    if isinstance(fields.get("skills"), list):
        fields["skills"] = "\n".join(
            str(item).strip() for item in fields["skills"] if str(item).strip()
        )
    for stat in set(_STAT_ALIASES.values()):
        if stat not in fields:
            continue
        try:
            fields[stat] = int(fields[stat])
        except (TypeError, ValueError) as error:
            raise ValidationError(f"Стат {stat} должен быть целым числом.") from error
