from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from bot.database.models import (
    Card,
    CardOwnership,
    CardUsage,
    Character,
    CharacterArt,
    CharacterTrophy,
    Contour,
    ContourComponent,
    ShakeiTransaction,
)
from bot.services.errors import ValidationError

MAX_ROWS = 50
MAX_OFFSET = 10_000
MAX_FILTERS = 12
MAX_SORTS = 3
MAX_IN_VALUES = 50
MAX_CELL_LENGTH = 2_000
MAX_RESULT_LENGTH = 9_000

QUERY_ENTITIES = {
    "characters": Character,
    "character_arts": CharacterArt,
    "character_trophies": CharacterTrophy,
    "cards": Card,
    "card_ownerships": CardOwnership,
    "card_usages": CardUsage,
    "contours": Contour,
    "contour_components": ContourComponent,
    "shakei_transactions": ShakeiTransaction,
}


async def query_database(
    session: AsyncSession, arguments: dict[str, object]
) -> dict[str, object]:
    """Выполняет ограниченную read-only выборку без возможности передать SQL."""
    entity = str(arguments.get("entity", "")).strip()
    model = QUERY_ENTITIES.get(entity)
    if model is None:
        raise ValidationError(
            "Неизвестная сущность выборки. Доступны: "
            + ", ".join(QUERY_ENTITIES)
            + "."
        )
    columns = {column.name: getattr(model, column.name) for column in model.__table__.columns}
    filters = _object_list(arguments.get("filters", []), "filters", MAX_FILTERS)
    conditions = [_condition(columns, item) for item in filters]
    mode = str(arguments.get("mode", "rows")).strip().casefold()
    if mode == "count":
        statement = select(func.count()).select_from(model).where(*conditions)
        return {"entity": entity, "mode": "count", "count": int(await session.scalar(statement) or 0)}
    if mode != "rows":
        raise ValidationError("Режим выборки должен быть rows или count.")

    field_names = _field_names(arguments.get("fields"), columns)
    limit = _bounded_int(arguments.get("limit", 20), "limit", 1, MAX_ROWS)
    offset = _bounded_int(arguments.get("offset", 0), "offset", 0, MAX_OFFSET)
    statement = select(*(columns[name] for name in field_names)).where(*conditions)
    sorts = _object_list(arguments.get("order_by", []), "order_by", MAX_SORTS)
    for item in sorts:
        field = str(item.get("field", ""))
        column = columns.get(field)
        if column is None:
            raise ValidationError(f"Сортировка по неизвестному полю: {field or 'без имени'}.")
        direction = str(item.get("direction", "asc")).casefold()
        if direction not in {"asc", "desc"}:
            raise ValidationError("Направление сортировки должно быть asc или desc.")
        statement = statement.order_by(column.desc() if direction == "desc" else column.asc())
    if not sorts:
        statement = statement.order_by(columns["id"].asc())
    raw_rows = (
        await session.execute(statement.offset(offset).limit(limit + 1))
    ).mappings().all()
    rows: list[dict[str, object]] = []
    result_length = 0
    for raw_row in raw_rows[:limit]:
        row = {name: _json_value(raw_row[name]) for name in field_names}
        row_length = len(json.dumps(row, ensure_ascii=False, default=str))
        if rows and result_length + row_length > MAX_RESULT_LENGTH:
            break
        rows.append(row)
        result_length += row_length
    has_more = len(raw_rows) > limit or len(rows) < min(len(raw_rows), limit)
    return {
        "entity": entity,
        "mode": "rows",
        "fields": field_names,
        "offset": offset,
        "limit": limit,
        "returned": len(rows),
        "has_more": has_more,
        "next_offset": offset + len(rows) if has_more else None,
        "rows": rows,
    }


def _condition(columns: dict[str, ColumnElement], item: dict[str, object]) -> ColumnElement:
    field = str(item.get("field", ""))
    column = columns.get(field)
    if column is None:
        raise ValidationError(f"Фильтр по неизвестному полю: {field or 'без имени'}.")
    operator = str(item.get("op", "eq")).casefold()
    value = item.get("value")
    if operator == "is_null":
        if not isinstance(value, bool):
            raise ValidationError("Для is_null поле value должно быть true или false.")
        return column.is_(None) if value else column.is_not(None)
    if operator == "contains":
        return column.contains(str(value or ""), autoescape=True)
    if operator == "starts_with":
        return column.startswith(str(value or ""), autoescape=True)
    if operator == "in":
        if not isinstance(value, list) or not 1 <= len(value) <= MAX_IN_VALUES:
            raise ValidationError(f"Для in нужен список от 1 до {MAX_IN_VALUES} значений.")
        return column.in_([_coerce_value(column, entry) for entry in value])
    converted = _coerce_value(column, value)
    if operator == "eq":
        return column == converted
    if operator == "ne":
        return column != converted
    if operator == "gt":
        return column > converted
    if operator == "gte":
        return column >= converted
    if operator == "lt":
        return column < converted
    if operator == "lte":
        return column <= converted
    raise ValidationError(
        "Неизвестный оператор фильтра. Доступны: eq, ne, contains, "
        "starts_with, in, gt, gte, lt, lte, is_null."
    )


def _coerce_value(column: ColumnElement, value: object) -> object:
    enum_class = getattr(column.type, "enum_class", None)
    if enum_class is not None and isinstance(value, str):
        for member in enum_class:
            if value.casefold() in {member.name.casefold(), str(member.value).casefold()}:
                return member
        raise ValidationError(f"Недопустимое значение {value!r} для поля {column.key}.")
    python_type = getattr(column.type, "python_type", None)
    try:
        if value is None or python_type is None or isinstance(value, python_type):
            return value
        if python_type is bool and isinstance(value, str):
            normalized = value.casefold()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
            raise ValueError
        if python_type is datetime and isinstance(value, str):
            return datetime.fromisoformat(value)
        return python_type(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"Некорректное значение для поля {column.key}.") from error


def _field_names(raw: object, columns: dict[str, ColumnElement]) -> list[str]:
    if raw is None:
        return list(columns)
    if not isinstance(raw, list) or not raw:
        raise ValidationError("fields должен быть непустым списком названий полей.")
    names = [str(value) for value in raw]
    unknown = [name for name in names if name not in columns]
    if unknown:
        raise ValidationError("Неизвестные поля выборки: " + ", ".join(unknown) + ".")
    return list(dict.fromkeys(names))


def _object_list(raw: object, name: str, maximum: int) -> list[dict[str, object]]:
    if not isinstance(raw, list) or len(raw) > maximum or any(not isinstance(item, dict) for item in raw):
        raise ValidationError(f"{name} должен быть списком не более чем из {maximum} объектов.")
    return raw


def _bounded_int(raw: object, name: str, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{name} должен быть целым числом.") from error
    if not minimum <= value <= maximum:
        raise ValidationError(f"{name} должен быть от {minimum} до {maximum}.")
    return value


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str) and len(value) > MAX_CELL_LENGTH:
        return value[: MAX_CELL_LENGTH - 1] + "…"
    return value
