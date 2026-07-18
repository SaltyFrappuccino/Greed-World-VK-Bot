from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import admin_ai as ai_crud
from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import contours as contours_crud
from bot.database.models import AdminAIPlan, AdminAISession, Card, CardType, Character, Rarity
from bot.services import (
    ai_service,
    auth_service,
    backup_service,
    card_service,
    character_service,
    contour_service,
    database_query_service,
    shakei_service,
    spreadsheet_service,
)
from bot.services.errors import NotFoundError, PermissionDenied, ServiceError, ValidationError
from bot.utils.formatters import vk_plain_text

MAX_ACTIONS = 20
MAX_TOOL_ROUNDS = 10
DESTRUCTIVE_TOOLS = {"character_delete", "card_delete", "contour_disassemble"}
READ_TOOLS = {
    "find_character",
    "list_characters",
    "get_character",
    "find_card",
    "list_cards",
    "get_card",
    "get_shakei_history",
    "query_database",
    "export_character",
    "export_character_cards",
    "export_registry",
    "create_backup",
}
WRITE_TOOLS = {
    "character_create",
    "character_update",
    "character_delete",
    "character_approve",
    "character_set_stat",
    "character_set_rating",
    "character_change_owner",
    "card_create",
    "card_create_and_grant",
    "card_update",
    "card_delete",
    "card_grant",
    "card_revoke",
    "ordinary_card_grant",
    "ordinary_card_revoke",
    "contour_create",
    "contour_update",
    "contour_disassemble",
    "contour_limit_set",
    "contour_capacity_set",
    "contour_card_add",
    "contour_card_remove",
    "contour_card_replace",
    "shakei_change",
}
ACTION_FIELDS = {
    "character_create": ({"vk_id", "name", "fields"}, {"vk_id", "name"}),
    "character_update": ({"character_id", "fields"}, {"character_id", "fields"}),
    "character_delete": ({"character_id"}, {"character_id"}),
    "character_approve": ({"character_id"}, {"character_id"}),
    "character_set_stat": ({"character_id", "stat", "value"}, {"character_id", "stat", "value"}),
    "character_set_rating": ({"character_id", "rating"}, {"character_id", "rating"}),
    "character_change_owner": ({"character_id", "vk_id"}, {"character_id", "vk_id"}),
    "card_create": ({"name", "card_type", "kind", "rarity", "number", "description", "usage", "transform_limit"}, {"name", "card_type", "kind", "rarity"}),
    "card_create_and_grant": ({"character_id", "name", "card_type", "kind", "rarity", "number", "description", "usage", "transform_limit"}, {"character_id", "name", "card_type", "kind", "rarity"}),
    "card_update": ({"card_id", "fields"}, {"card_id", "fields"}),
    "card_delete": ({"card_id"}, {"card_id"}),
    "card_grant": ({"character_id", "card_id"}, {"character_id", "card_id"}),
    "card_revoke": ({"character_id", "card_id"}, {"character_id", "card_id"}),
    "ordinary_card_grant": ({"character_id", "name", "kind", "rarity", "description", "usage"}, {"character_id", "name", "kind", "rarity"}),
    "ordinary_card_revoke": ({"character_id", "ownership_id"}, {"character_id", "ownership_id"}),
    "contour_create": ({"character_id", "ownership_ids", "name", "slot", "card_capacity", "fields"}, {"character_id", "ownership_ids", "name"}),
    "contour_update": ({"contour_id", "fields"}, {"contour_id", "fields"}),
    "contour_disassemble": ({"contour_id"}, {"contour_id"}),
    "contour_limit_set": ({"character_id", "value"}, {"character_id", "value"}),
    "contour_capacity_set": ({"contour_id", "value"}, {"contour_id", "value"}),
    "contour_card_add": ({"contour_id", "ownership_id"}, {"contour_id", "ownership_id"}),
    "contour_card_remove": ({"contour_id", "component_id"}, {"contour_id", "component_id"}),
    "contour_card_replace": ({"contour_id", "component_id", "ownership_id"}, {"contour_id", "component_id", "ownership_id"}),
    "shakei_change": ({"character_id", "delta"}, {"character_id", "delta"}),
}
CHARACTER_CREATE_FIELDS = {
    "age", "gender", "appearance", "personality", "biography", "skills", "additional",
    "stress_resistance", "speech", "intuition", "spine", "will", "scent",
    "overall_rating", "is_approved", "contour_limit",
}
CHARACTER_UPDATE_FIELDS = {
    "name", "vk_id", "age", "gender", "appearance", "personality", "biography", "skills", "additional",
}
CARD_UPDATE_FIELDS = {"name", "kind", "rarity", "number", "description", "usage", "transform_limit"}


@dataclass(frozen=True)
class AssistantAttachment:
    filename: str
    data: bytes


@dataclass(frozen=True)
class AssistantOutcome:
    text: str
    plan: AdminAIPlan | None = None
    attachments: tuple[AssistantAttachment, ...] = ()


async def open_session(
    session: AsyncSession, *, admin_vk_id: int, peer_id: int
) -> AdminAISession:
    auth_service.require_admin(admin_vk_id)
    return await ai_crud.get_or_create_session(
        session, admin_vk_id=admin_vk_id, peer_id=peer_id
    )


async def close_session(
    session: AsyncSession, *, session_id: int, admin_vk_id: int, peer_id: int
) -> None:
    auth_service.require_admin(admin_vk_id)
    item = await ai_crud.get_owned_session(
        session, session_id=session_id, admin_vk_id=admin_vk_id, peer_id=peer_id
    )
    if item is None:
        raise PermissionDenied("AI-сессия не найдена или принадлежит другому администратору.")
    await ai_crud.supersede_open_plans(session, item.id)
    await ai_crud.close_session(session, item)


async def start_new_session(
    session: AsyncSession, *, session_id: int, admin_vk_id: int, peer_id: int
) -> AdminAISession:
    auth_service.require_admin(admin_vk_id)
    current = await _owned_session(session, session_id, admin_vk_id, peer_id)
    await ai_crud.supersede_open_plans(session, current.id)
    await ai_crud.close_session(session, current)
    return await ai_crud.get_or_create_session(
        session, admin_vk_id=admin_vk_id, peer_id=peer_id
    )


async def history_text(
    session: AsyncSession, *, session_id: int, admin_vk_id: int, peer_id: int
) -> str:
    item = await _owned_session(session, session_id, admin_vk_id, peer_id)
    messages = await ai_crud.list_admin_messages(
        session, admin_vk_id=admin_vk_id, peer_id=peer_id, limit=20
    )
    if not messages:
        return "История AI-Ассистента пока пуста."
    labels = {"user": "Вы", "assistant": "AI", "tool": "Инструмент", "system": "Система"}
    return "Последние сообщения:\n\n" + "\n\n".join(
        f"{labels.get(message.role, message.role)}: {vk_plain_text(message.content)}"
        for message in messages
    )


async def process_message(
    session: AsyncSession,
    *,
    session_id: int,
    admin_vk_id: int,
    peer_id: int,
    text: str,
    image_urls: list[str] | None = None,
) -> AssistantOutcome:
    auth_service.require_admin(admin_vk_id)
    ai_session = await _owned_session(session, session_id, admin_vk_id, peer_id)
    if ai_session.status != "active":
        raise ValidationError("AI-сессия уже закрыта.")
    if not text.strip() and not image_urls:
        raise ValidationError("Пришлите текстовую просьбу или изображение.")
    await ai_crud.add_message(
        session,
        session_id=ai_session.id,
        role="user",
        content=text.strip() or "[Изображение без текста]",
        details={"image_count": len(image_urls or [])},
    )

    attachments: list[AssistantAttachment] = []
    for round_number in range(MAX_TOOL_ROUNDS):
        history = await _model_history(session, ai_session.id)
        turn = await ai_service.generate_admin_assistant_turn(
            history,
            image_urls=image_urls if round_number == 0 else None,
        )
        if turn.kind == "clarification":
            policy_error = _clarification_policy_error(text, turn.message)
            if policy_error:
                await ai_crud.add_message(
                    session,
                    session_id=ai_session.id,
                    role="tool",
                    content=(
                        "Исправь уточнение и ответь заново. Это сообщение не было "
                        f"показано пользователю. Нарушение: {policy_error}"
                    ),
                    details={"clarification_rejected": True},
                )
                continue
        if turn.kind in {"answer", "clarification"}:
            response_text = vk_plain_text(turn.message)
            await ai_crud.add_message(
                session, session_id=ai_session.id, role="assistant", content=response_text
            )
            return AssistantOutcome(response_text, attachments=tuple(attachments))
        if turn.kind == "read_tools":
            if not turn.tools:
                raise ValidationError("AI запросил чтение, но не указал инструменты.")
            results = []
            for tool in turn.tools:
                try:
                    result, attachment = await _run_read_tool(
                        session, tool.name, tool.arguments
                    )
                    observation = {"tool": tool.name, "ok": True, "result": result}
                except ServiceError as error:
                    attachment = None
                    observation = await _failed_read_observation(
                        session, tool.name, tool.arguments, error
                    )
                results.append(observation)
                if attachment is not None:
                    attachments.append(attachment)
            tool_text = (
                "Наблюдения после выполнения read-инструментов. "
                "Проанализируй их и сам выбери следующий шаг; не показывай "
                "пользователю внутренние рассуждения:\n"
                + json.dumps(results, ensure_ascii=False)
            )
            await ai_crud.add_message(
                session,
                session_id=ai_session.id,
                role="tool",
                content=tool_text,
                details={"results": results},
            )
            continue
        if turn.kind == "action_plan":
            if not turn.actions:
                raise ValidationError("AI предложил пустой план.")
            actions = [
                {
                    **action.model_dump(mode="json"),
                    "description": vk_plain_text(action.description),
                }
                for action in turn.actions
            ]
            plan = await create_plan(
                session,
                ai_session=ai_session,
                admin_vk_id=admin_vk_id,
                summary=vk_plain_text(turn.message),
                actions=actions,
                warnings=[vk_plain_text(item) for item in turn.warnings],
            )
            await ai_crud.add_message(
                session,
                session_id=ai_session.id,
                role="assistant",
                content=format_plan(plan),
                details={"plan_id": plan.id},
            )
            return AssistantOutcome(format_plan(plan), plan=plan, attachments=tuple(attachments))
    raise ValidationError("AI превысил лимит обращений к инструментам. Уточните просьбу.")


async def create_plan(
    session: AsyncSession,
    *,
    ai_session: AdminAISession,
    admin_vk_id: int,
    summary: str,
    actions: list[dict[str, object]],
    warnings: list[str],
) -> AdminAIPlan:
    auth_service.require_admin(admin_vk_id)
    if ai_session.admin_vk_id != admin_vk_id or ai_session.status != "active":
        raise PermissionDenied("Нельзя создать план в чужой или закрытой AI-сессии.")
    if not 1 <= len(actions) <= MAX_ACTIONS:
        raise ValidationError(f"В плане должно быть от 1 до {MAX_ACTIONS} действий.")
    snapshot: dict[str, object] = {}
    for action in actions:
        name = str(action.get("name", ""))
        arguments = action.get("arguments")
        if name not in WRITE_TOOLS or not isinstance(arguments, dict):
            raise ValidationError(f"AI запросил неизвестный изменяющий инструмент: {name or 'без имени'}.")
        _validate_action_arguments(name, arguments)
        snapshot.update(await _action_snapshot(session, name, arguments))
    destructive = any(str(action["name"]) in DESTRUCTIVE_TOOLS for action in actions)
    return await ai_crud.create_plan(
        session,
        session_id=ai_session.id,
        admin_vk_id=admin_vk_id,
        summary=summary.strip() or "Изменение игровых данных",
        actions=actions,
        snapshot=snapshot,
        warnings=warnings,
        destructive=destructive,
    )


async def confirm_plan(
    session: AsyncSession,
    *,
    plan_id: int,
    admin_vk_id: int,
    peer_id: int,
    destructive_confirmed: bool = False,
) -> tuple[AdminAIPlan, bool]:
    auth_service.require_admin(admin_vk_id)
    plan = await ai_crud.get_plan_for_update(
        session, plan_id=plan_id, admin_vk_id=admin_vk_id
    )
    if plan is None:
        raise PermissionDenied("AI-план не найден или принадлежит другому администратору.")
    ai_session = await _owned_session(session, plan.session_id, admin_vk_id, peer_id)
    if ai_session.status != "active":
        raise ValidationError("AI-сессия уже закрыта.")
    if plan.status == "executed":
        raise ValidationError("Этот план уже выполнен.")
    if plan.status not in {"proposed", "awaiting_destructive_confirmation"}:
        raise ValidationError("Этот план уже недоступен для выполнения.")
    if plan.destructive and not destructive_confirmed:
        plan.status = "awaiting_destructive_confirmation"
        plan.confirmed_at = datetime.now(timezone.utc)
        await session.flush()
        return plan, False
    if plan.destructive and plan.status != "awaiting_destructive_confirmation":
        raise ValidationError("Сначала подтвердите предупреждение об удалении.")

    current_snapshot: dict[str, object] = {}
    for action in plan.actions:
        current_snapshot.update(
            await _action_snapshot(session, str(action["name"]), dict(action["arguments"]))
        )
    if current_snapshot != plan.snapshot:
        plan.status = "failed"
        plan.error = "Данные изменились после создания плана."
        await session.flush()
        raise ValidationError("Данные изменились после создания плана. Попросите AI пересобрать его.")

    plan.status = "executing"
    plan.confirmed_at = datetime.now(timezone.utc)
    results = []
    async with session.begin_nested():
        for action in plan.actions:
            auth_service.require_admin(admin_vk_id)
            results.append(
                await _execute_action(
                    session,
                    str(action["name"]),
                    dict(action["arguments"]),
                    admin_vk_id=admin_vk_id,
                    plan_id=plan.id,
                )
            )
    plan.status = "executed"
    plan.result = {"actions": results}
    plan.executed_at = datetime.now(timezone.utc)
    await ai_crud.add_message(
        session,
        session_id=ai_session.id,
        role="system",
        content=format_result(plan),
        details=plan.result,
    )
    await session.flush()
    return plan, True


async def cancel_plan(
    session: AsyncSession, *, plan_id: int, admin_vk_id: int, peer_id: int
) -> AdminAIPlan:
    auth_service.require_admin(admin_vk_id)
    plan = await ai_crud.get_plan_for_update(session, plan_id=plan_id, admin_vk_id=admin_vk_id)
    if plan is None:
        raise PermissionDenied("AI-план не найден.")
    await _owned_session(session, plan.session_id, admin_vk_id, peer_id)
    if plan.status not in {"proposed", "awaiting_destructive_confirmation"}:
        raise ValidationError("Этот план уже нельзя отменить.")
    plan.status = "cancelled"
    await session.flush()
    return plan


async def mark_plan_failed(
    session: AsyncSession, *, plan_id: int, admin_vk_id: int, error: str
) -> None:
    auth_service.require_admin(admin_vk_id)
    plan = await ai_crud.get_plan_for_update(
        session, plan_id=plan_id, admin_vk_id=admin_vk_id
    )
    if plan is not None and plan.status != "executed":
        plan.status = "failed"
        plan.error = error[:2000]
        await session.flush()


def format_plan(plan: AdminAIPlan) -> str:
    lines = [f"AI-план #{plan.id}", vk_plain_text(plan.summary), "", "Действия:"]
    for index, action in enumerate(plan.actions, start=1):
        description = vk_plain_text(str(action.get("description") or action["name"]))
        lines.append(f"{index}. {description}")
        lines.extend(f"   {line}" for line in _action_preview(plan, action))
    if plan.warnings:
        lines.extend(
            ["", "Предупреждения:", *(f"• {vk_plain_text(str(item))}" for item in plan.warnings)]
        )
    if plan.destructive:
        lines.extend(["", "⚠ План содержит необратимое удаление и потребует второго подтверждения."])
    lines.append("\nДо подтверждения в базе ничего не изменено.")
    return "\n".join(lines)


def _action_preview(
    plan: AdminAIPlan, action: dict[str, object]
) -> list[str]:
    name = str(action["name"])
    arguments = dict(action.get("arguments", {}))
    target: dict[str, object] = {}
    if "character_id" in arguments:
        target = dict(plan.snapshot.get(f"character:{arguments['character_id']}", {}))
    elif "card_id" in arguments:
        target = dict(plan.snapshot.get(f"card:{arguments['card_id']}", {}))
    elif "contour_id" in arguments:
        target = dict(plan.snapshot.get(f"contour:{arguments['contour_id']}", {}))

    fields = arguments.get("fields")
    if isinstance(fields, dict) and fields:
        return [
            f"{field}: {_display(target.get(field))} → {_display(value)}"
            for field, value in fields.items()
        ]
    stat_name = str(arguments.get("stat", "стат"))
    try:
        stat_field = character_service.resolve_stat(stat_name)
    except ValidationError:
        stat_field = stat_name
    simple_change = {
        "character_set_stat": (stat_field, arguments.get("value")),
        "character_set_rating": ("rating", arguments.get("rating")),
        "character_change_owner": ("vk_id", arguments.get("vk_id")),
        "contour_limit_set": ("contour_limit", arguments.get("value")),
        "contour_capacity_set": ("capacity", arguments.get("value")),
    }.get(name)
    if simple_change:
        field, value = simple_change
        return [f"{field}: {_display(target.get(field))} → {_display(value)}"]
    if name == "shakei_change":
        before = int(target.get("shakei", 0))
        delta = int(arguments.get("delta", 0))
        return [f"Шакеи: {before} → {before + delta} ({delta:+d})"]
    if name.endswith("_delete") or name == "contour_disassemble":
        return [f"Будет удалено: #{target.get('id', '?')} · {target.get('name', 'без названия')}"]
    safe_arguments = {
        key: value
        for key, value in arguments.items()
        if key not in {"fields"}
    }
    return [
        "Параметры: "
        + json.dumps(safe_arguments, ensure_ascii=False, sort_keys=True)
    ]


def _display(value: object) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def format_result(plan: AdminAIPlan) -> str:
    results = plan.result.get("actions", [])
    return f"AI-план #{plan.id} выполнен.\n\n" + "\n".join(
        f"{index}. {result}" for index, result in enumerate(results, start=1)
    )


async def _owned_session(
    session: AsyncSession, session_id: int, admin_vk_id: int, peer_id: int
) -> AdminAISession:
    item = await ai_crud.get_owned_session(
        session, session_id=session_id, admin_vk_id=admin_vk_id, peer_id=peer_id
    )
    if item is None:
        raise PermissionDenied("AI-сессия не найдена или принадлежит другому администратору.")
    return item


async def _model_history(session: AsyncSession, session_id: int) -> list[dict[str, str]]:
    messages = await ai_crud.list_messages(session, session_id, limit=30)
    result = []
    total = 0
    for message in reversed(messages):
        content = message.content[-12000:]
        if total + len(content) > 24000:
            break
        role = "assistant" if message.role == "assistant" else "user"
        result.append({"role": role, "content": content})
        total += len(content)
    return list(reversed(result))


async def _run_read_tool(
    session: AsyncSession, name: str, arguments: dict[str, object]
) -> tuple[object, AssistantAttachment | None]:
    if name not in READ_TOOLS:
        raise ValidationError(f"AI запросил неизвестный read-инструмент: {name}.")
    if name == "find_character":
        return _character_data(await character_service.find_character(session, _text(arguments, "query"))), None
    if name == "list_characters":
        owner = arguments.get("owner_vk_id")
        query = str(arguments.get("query", "")).strip()
        if owner is not None:
            items = await characters_crud.list_by_vk_id(session, int(owner))
        elif query:
            items = await characters_crud.search_by_name(session, query, limit=20)
        else:
            items = await characters_crud.list_characters(session, limit=20, approved_only=False)
        return [_character_data(item) for item in items], None
    if name == "get_character":
        character = await _character(session, _integer(arguments, "character_id"))
        ownerships = await cards_crud.list_character_ownerships(session, character.id)
        contours = await contours_crud.list_for_character(session, character.id)
        data = _character_data(character)
        data["cards"] = [
            {"ownership_id": item.id, "name": item.display_name, "type": item.display_type.value, "bound": item.contour_component is not None}
            for item in ownerships
        ]
        data["contours"] = [
            {"id": item.id, "slot": item.slot, "name": item.name, "capacity": item.card_capacity, "components": [component.card_ownership_id for component in item.components]}
            for item in contours
        ]
        return data, None
    if name == "find_card":
        return _card_data(await card_service.find_card(session, _text(arguments, "query"))), None
    if name == "list_cards":
        items = await cards_crud.list_cards(session, limit=50)
        query = str(arguments.get("query", "")).strip().casefold()
        card_type = str(arguments.get("card_type", "")).strip()
        if query:
            items = [item for item in items if query in item.name.casefold()]
        if card_type:
            expected = _card_type(card_type)
            items = [item for item in items if item.card_type is expected]
        return [_card_data(item) for item in items], None
    if name == "get_card":
        card = await _card(session, _integer(arguments, "card_id"))
        data = _card_data(card)
        ownerships = await cards_crud.list_card_ownerships(session, card.id)
        data["live_copies"] = len(ownerships)
        data["owners"] = [
            {
                "ownership_id": item.id,
                "character_id": item.character_id,
                "character_name": item.character.name,
                "bound_contour_id": (
                    item.contour_component.contour_id
                    if item.contour_component is not None
                    else None
                ),
            }
            for item in ownerships
        ]
        return data, None
    if name == "get_shakei_history":
        character_id = _integer(arguments, "character_id")
        await _character(session, character_id)
        items = await shakei_service.history(session, character_id, limit=20)
        return [{"amount": item.amount, "from": item.from_character_id, "to": item.to_character_id, "created_at": str(item.created_at)} for item in items], None
    if name == "query_database":
        return await database_query_service.query_database(session, arguments), None
    if name == "export_character":
        export = await spreadsheet_service.export_character_profile(session, _integer(arguments, "character_id"))
    elif name == "export_character_cards":
        export = await spreadsheet_service.export_character_cards(session, _integer(arguments, "character_id"))
    elif name == "export_registry":
        export = await spreadsheet_service.export_registry(session)
    else:
        backup = await backup_service.create_database_backup()
        return {"filename": backup.filename, "ready": True}, AssistantAttachment(backup.filename, backup.data)
    return {"filename": export.filename, "ready": True}, AssistantAttachment(export.filename, export.data)


async def _failed_read_observation(
    session: AsyncSession,
    name: str,
    arguments: dict[str, object],
    error: ServiceError,
) -> dict[str, object]:
    observation: dict[str, object] = {
        "tool": name,
        "ok": False,
        "error": str(error),
        "instruction": "Это наблюдение, а не окончательный ответ. Попробуй другой read-инструмент или запрос.",
    }
    query = str(arguments.get("query", "")).strip()
    if not query:
        return observation
    if name == "find_character":
        candidates = await characters_crud.list_characters(
            session, limit=100, approved_only=False
        )
        suggestions = _closest_named(query, candidates)
        if suggestions:
            observation["close_matches"] = [
                {"id": item.id, "name": item.name, "vk_id": item.vk_id}
                for item in suggestions
            ]
    elif name == "find_card":
        candidates = await cards_crud.list_cards(session, limit=100)
        suggestions = _closest_named(query, candidates)
        if suggestions:
            observation["close_matches"] = [
                {"id": item.id, "name": item.name, "card_type": item.card_type.value}
                for item in suggestions
            ]
    return observation


def _closest_named(query: str, items: list[Character] | list[Card]) -> list[Character] | list[Card]:
    expected = query.casefold()
    ranked = sorted(
        (
            (SequenceMatcher(None, expected, item.name.casefold()).ratio(), item)
            for item in items
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [item for score, item in ranked[:5] if score >= 0.35]


def _clarification_policy_error(user_text: str, question: str) -> str | None:
    normalized_question = question.casefold()
    forbidden_rarities = (
        "эпическ",
        "легендарн",
        "необычн",
    )
    if any(value in normalized_question for value in forbidden_rarities):
        return "использована чужая шкала редкости; допустимы только H–SS"

    normalized_user = user_text.casefold()
    creative_request = any(
        marker in normalized_user
        for marker in (
            "придум",
            "сам реши",
            "сама реши",
            "пофиг",
            "на твой выбор",
            "что угодно",
        )
    )
    if creative_request:
        unnecessary_topics = (
            "редкост",
            "описан",
            "характеристик",
            "эффект",
            "лимит",
            "номер слот",
        )
        if any(topic in normalized_question for topic in unnecessary_topics):
            return "запрошены творческие параметры, которые пользователь поручил выбрать агенту"

    explicit_registry_type = bool(
        re.search(r"\b(заклинан\w*|контурн\w*|особ\w*\s+карт\w*)\b", normalized_user)
    )
    asks_registry_choice = "реестр" in normalized_question and "обычн" in normalized_question
    if explicit_registry_type and asks_registry_choice:
        return "тип карты уже означает реестровую карту; выбирать между реестром и Обычной не нужно"
    return None


async def _action_snapshot(
    session: AsyncSession, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    result: dict[str, object] = {}
    if "character_id" in arguments:
        character = await _character(session, int(arguments["character_id"]))
        result[f"character:{character.id}"] = _character_data(character)
        if name == "character_delete":
            ownerships = await cards_crud.list_character_ownerships(session, character.id)
            contours = await contours_crud.list_for_character(session, character.id)
            result[f"character_contents:{character.id}"] = {
                "ownership_ids": [item.id for item in ownerships],
                "contour_ids": [item.id for item in contours],
            }
    if "card_id" in arguments:
        card = await _card(session, int(arguments["card_id"]))
        ownerships = await cards_crud.list_card_ownerships(session, card.id)
        result[f"card:{card.id}"] = _card_data(card) | {
            "live_copies": len(ownerships),
            "ownerships": [
                {
                    "id": item.id,
                    "character_id": item.character_id,
                    "bound_contour_id": (
                        item.contour_component.contour_id
                        if item.contour_component is not None
                        else None
                    ),
                }
                for item in ownerships
            ],
        }
    if "contour_id" in arguments:
        contour = await contours_crud.get_by_id(session, int(arguments["contour_id"]))
        if contour is None:
            raise NotFoundError("Контур не найден.")
        result[f"contour:{contour.id}"] = {
            "id": contour.id,
            "character_id": contour.character_id,
            "slot": contour.slot,
            "capacity": contour.card_capacity,
            "name": contour.name,
            "components": [item.card_ownership_id for item in contour.components],
            **{field: getattr(contour, field) for field in contour_service.EDITABLE_FIELDS},
        }
    if "ownership_id" in arguments:
        ownership_id = int(arguments["ownership_id"])
        ownership = await cards_crud.get_ownership_by_id(session, ownership_id)
        if ownership is None:
            raise NotFoundError(f"Копия карты #{ownership_id} не найдена.")
        result[f"ownership:{ownership_id}"] = {
            "id": ownership.id,
            "character_id": ownership.character_id,
            "card_id": ownership.card_id,
            "name": ownership.display_name,
            "bound_contour_id": (
                ownership.contour_component.contour_id
                if ownership.contour_component is not None
                else None
            ),
        }
    if "component_id" in arguments:
        component_id = int(arguments["component_id"])
        component = await contours_crud.get_component(session, component_id)
        if component is None:
            raise NotFoundError(f"Компонент Контура #{component_id} не найден.")
        result[f"component:{component_id}"] = {
            "id": component.id,
            "contour_id": component.contour_id,
            "ownership_id": component.card_ownership_id,
            "position": component.position,
        }
    for raw_ownership_id in arguments.get("ownership_ids", []):
        ownership_id = int(raw_ownership_id)
        ownership = await cards_crud.get_ownership_by_id(session, ownership_id)
        if ownership is None:
            raise NotFoundError(f"Копия карты #{ownership_id} не найдена.")
        result[f"ownership:{ownership_id}"] = {
            "id": ownership.id,
            "character_id": ownership.character_id,
            "card_id": ownership.card_id,
            "name": ownership.display_name,
            "bound_contour_id": (
                ownership.contour_component.contour_id
                if ownership.contour_component is not None
                else None
            ),
        }
    return result


async def _execute_action(
    session: AsyncSession,
    name: str,
    arguments: dict[str, object],
    *,
    admin_vk_id: int,
    plan_id: int,
) -> str:
    if name == "character_create":
        fields = _normalize_character_create_fields(_dict(arguments, "fields", optional=True))
        item = await character_service.create_character(session, vk_id=_integer(arguments, "vk_id"), name=_text(arguments, "name"), **fields)
        return f"Создана анкета #{item.id} · {item.name}."
    if name == "character_update":
        item = await _character(session, _integer(arguments, "character_id"))
        fields = _dict(arguments, "fields")
        _reject_unknown_fields(fields, CHARACTER_UPDATE_FIELDS, "анкеты")
        if "name" in fields:
            await character_service.rename_character(session, item, str(fields.pop("name")))
        if "vk_id" in fields:
            await character_service.change_owner(session, item, int(fields.pop("vk_id")))
        if fields:
            await character_service.update_profile(session, item, **fields)
        return f"Обновлена анкета #{item.id} · {item.name}."
    if name == "character_delete":
        item_id = _integer(arguments, "character_id")
        return f"Удалена анкета #{item_id} · {await character_service.delete_character(session, item_id)}."
    if name == "character_approve":
        item = await character_service.approve(session, _integer(arguments, "character_id"))
        return f"Подтверждена анкета #{item.id} · {item.name}."
    if name == "character_set_stat":
        item = await character_service.set_stat(session, _integer(arguments, "character_id"), _text(arguments, "stat"), _integer(arguments, "value"))
        return f"Изменён стат анкеты #{item.id}."
    if name == "character_set_rating":
        item = await character_service.set_rating(session, _integer(arguments, "character_id"), _rarity(arguments["rating"]))
        return f"Рейтинг анкеты #{item.id}: {item.overall_rating.value}."
    if name == "character_change_owner":
        item = await _character(session, _integer(arguments, "character_id"))
        await character_service.change_owner(session, item, _integer(arguments, "vk_id"))
        return f"Владелец анкеты #{item.id} изменён."
    if name == "card_create":
        item = await card_service.create_card(
            session,
            name=_text(arguments, "name"), card_type=_card_type(arguments["card_type"]),
            kind=_text(arguments, "kind"), rarity=_rarity(arguments["rarity"]), admin_vk_id=admin_vk_id,
            number=_optional_int(arguments.get("number")), description=str(arguments.get("description", "")),
            usage=str(arguments.get("usage", "")), transform_limit=_optional_int(arguments.get("transform_limit")),
        )
        return f"Создана карта #{item.id} · {item.name}."
    if name == "card_create_and_grant":
        character_id = _integer(arguments, "character_id")
        item = await card_service.create_card(
            session,
            name=_text(arguments, "name"), card_type=_card_type(arguments["card_type"]),
            kind=_text(arguments, "kind"), rarity=_rarity(arguments["rarity"]), admin_vk_id=admin_vk_id,
            number=_optional_int(arguments.get("number")), description=str(arguments.get("description", "")),
            usage=str(arguments.get("usage", "")), transform_limit=_optional_int(arguments.get("transform_limit")),
        )
        ownership = await card_service.grant_card(session, item.id, character_id)
        return (
            f"Создана карта #{item.id} · {item.name} и выдана персонажу "
            f"#{character_id}; копия владения #{ownership.id}."
        )
    if name == "card_update":
        fields = _dict(arguments, "fields")
        _reject_unknown_fields(fields, CARD_UPDATE_FIELDS, "карты")
        item = await card_service.update_card(session, _integer(arguments, "card_id"), **_normalize_card_fields(fields))
        return f"Обновлена карта #{item.id} · {item.name}."
    if name == "card_delete":
        item_id = _integer(arguments, "card_id")
        return f"Удалена карта #{item_id} · {await card_service.delete_card(session, item_id)}."
    if name == "card_grant":
        item = await card_service.grant_card(session, _integer(arguments, "card_id"), _integer(arguments, "character_id"))
        return f"Выдана копия владения #{item.id}."
    if name == "card_revoke":
        await card_service.revoke_card(session, _integer(arguments, "card_id"), _integer(arguments, "character_id"))
        return "Свободная копия карты забрана."
    if name == "ordinary_card_grant":
        item = await card_service.grant_ordinary_card(
            session, character_id=_integer(arguments, "character_id"), name=_text(arguments, "name"),
            kind=_text(arguments, "kind"), rarity=_rarity(arguments["rarity"]),
            description=str(arguments.get("description", "")), usage=str(arguments.get("usage", "")),
        )
        return f"Добавлена Обычная карта, владение #{item.id}."
    if name == "ordinary_card_revoke":
        ownership = await cards_crud.get_ownership_by_id(session, _integer(arguments, "ownership_id"))
        if ownership is None or ownership.card_id is not None:
            raise NotFoundError("Обычная карта не найдена.")
        await card_service.revoke_ordinary_card(session, character_id=ownership.character_id, name=ownership.display_name)
        return f"Обычная карта «{ownership.display_name}» забрана."
    if name == "contour_create":
        item = await contour_service.create_contour(
            session, character_id=_integer(arguments, "character_id"), ownership_ids=[int(value) for value in arguments.get("ownership_ids", [])],
            name=_text(arguments, "name"), admin_vk_id=admin_vk_id, slot=_optional_int(arguments.get("slot")),
            card_capacity=int(arguments.get("card_capacity", 2)), **_dict(arguments, "fields", optional=True),
        )
        return f"Создан Контур #{item.id} · {item.name}."
    if name == "contour_update":
        item = await contour_service.update_contour(session, contour_id=_integer(arguments, "contour_id"), admin_vk_id=admin_vk_id, **_dict(arguments, "fields"))
        return f"Обновлён Контур #{item.id} · {item.name}."
    if name == "contour_disassemble":
        item_id = _integer(arguments, "contour_id")
        _, title = await contour_service.disassemble(session, contour_id=item_id, admin_vk_id=admin_vk_id)
        return f"Разобран Контур #{item_id} · {title}."
    if name == "contour_limit_set":
        item = await contour_service.set_character_limit(session, character_id=_integer(arguments, "character_id"), value=_integer(arguments, "value"), admin_vk_id=admin_vk_id)
        return f"Лимит Контуров анкеты #{item.id}: {item.contour_limit}."
    if name == "contour_capacity_set":
        item = await contour_service.set_capacity(session, contour_id=_integer(arguments, "contour_id"), value=_integer(arguments, "value"), admin_vk_id=admin_vk_id)
        return f"Размер Контура #{item.id}: {item.card_capacity}."
    if name == "contour_card_add":
        item = await contour_service.add_card(session, contour_id=_integer(arguments, "contour_id"), ownership_id=_integer(arguments, "ownership_id"), admin_vk_id=admin_vk_id)
        return f"Карта добавлена в Контур #{item.id}."
    if name == "contour_card_remove":
        item = await contour_service.remove_card(session, component_id=_integer(arguments, "component_id"), admin_vk_id=admin_vk_id)
        return f"Карта убрана из Контура #{item.id}."
    if name == "contour_card_replace":
        item = await contour_service.replace_card(session, component_id=_integer(arguments, "component_id"), ownership_id=_integer(arguments, "ownership_id"), admin_vk_id=admin_vk_id)
        return f"Карта заменена в Контуре #{item.id}."
    if name == "shakei_change":
        character_id, delta = _integer(arguments, "character_id"), int(arguments.get("delta", 0))
        if delta == 0:
            raise ValidationError("Изменение Шакеев не может быть нулевым.")
        if delta > 0:
            await shakei_service.grant(session, character_id=character_id, amount=delta, admin_vk_id=admin_vk_id, reason=f"AI-план #{plan_id}")
        else:
            await shakei_service.deduct(session, character_id=character_id, amount=abs(delta), admin_vk_id=admin_vk_id, reason=f"AI-план #{plan_id}")
        item = await _character(session, character_id)
        return f"Шакеи анкеты #{item.id}: {delta:+d}; баланс {item.shakei_balance}."
    raise ValidationError(f"Неизвестный изменяющий инструмент: {name}.")


async def _character(session: AsyncSession, character_id: int) -> Character:
    item = await characters_crud.get_by_id(session, character_id)
    if item is None:
        raise NotFoundError(f"Анкета #{character_id} не найдена.")
    return item


async def _card(session: AsyncSession, card_id: int) -> Card:
    item = await cards_crud.get_by_id(session, card_id)
    if item is None:
        raise NotFoundError(f"Карта #{card_id} не найдена.")
    return item


def _character_data(item: Character) -> dict[str, object]:
    return {
        "id": item.id, "vk_id": item.vk_id, "name": item.name, "age": item.age,
        "gender": item.gender, "appearance": item.appearance, "personality": item.personality,
        "biography": item.biography, "skills": item.skills, "additional": item.additional,
        "stress_resistance": item.stress_resistance, "speech": item.speech,
        "intuition": item.intuition, "spine": item.spine, "will": item.will, "scent": item.scent,
        "rating": item.overall_rating.value, "shakei": item.shakei_balance,
        "contour_limit": item.contour_limit, "approved": item.is_approved,
    }


def _card_data(item: Card) -> dict[str, object]:
    return {
        "id": item.id, "number": item.number, "registry_number": item.registry_number,
        "name": item.name, "card_type": item.card_type.value, "kind": item.kind,
        "rarity": item.rarity.value, "description": item.description, "usage": item.usage,
        "transform_limit": item.transform_limit, "copies_count": item.copies_count,
    }


def _text(arguments: dict[str, object], key: str) -> str:
    value = str(arguments.get(key, "")).strip()
    if not value:
        raise ValidationError(f"Инструменту не передано поле {key}.")
    return value


def _integer(arguments: dict[str, object], key: str) -> int:
    try:
        value = int(arguments[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError(f"Поле {key} должно быть целым числом.") from error
    if value <= 0:
        raise ValidationError(f"Поле {key} должно быть больше нуля.")
    return value


def _optional_int(value: object) -> int | None:
    return None if value in (None, "") else int(value)


def _dict(arguments: dict[str, object], key: str, *, optional: bool = False) -> dict[str, object]:
    value = arguments.get(key, {} if optional else None)
    if not isinstance(value, dict):
        raise ValidationError(f"Поле {key} должно быть объектом.")
    return dict(value)


def _rarity(value: object) -> Rarity:
    try:
        return Rarity(str(value).upper())
    except ValueError as error:
        raise ValidationError("Неизвестная редкость карты.") from error


def _card_type(value: object) -> CardType:
    text = str(value).strip()
    for item in CardType:
        if text.casefold() in {item.name.casefold(), item.value.casefold()}:
            return item
    raise ValidationError("Неизвестный тип карты.")


def _normalize_card_fields(fields: dict[str, object]) -> dict[str, object]:
    if "rarity" in fields:
        fields["rarity"] = _rarity(fields["rarity"])
    if "card_type" in fields:
        raise ValidationError("Тип существующей карты менять нельзя.")
    return fields


def _normalize_character_create_fields(fields: dict[str, object]) -> dict[str, object]:
    _reject_unknown_fields(fields, CHARACTER_CREATE_FIELDS, "новой анкеты")
    if "overall_rating" in fields:
        fields["overall_rating"] = _rarity(fields["overall_rating"])
    return fields


def _reject_unknown_fields(
    fields: dict[str, object], allowed: set[str], target: str
) -> None:
    unknown = set(fields) - allowed
    if unknown:
        raise ValidationError(
            f"AI попытался изменить запрещённые поля {target}: {', '.join(sorted(unknown))}."
        )


def _validate_action_arguments(name: str, arguments: dict[str, object]) -> None:
    allowed, required = ACTION_FIELDS[name]
    unknown = set(arguments) - allowed
    missing = required - set(arguments)
    if unknown:
        raise ValidationError(
            f"Инструмент {name} получил запрещённые аргументы: {', '.join(sorted(unknown))}."
        )
    if missing:
        raise ValidationError(
            f"Инструмент {name} не получил обязательные аргументы: {', '.join(sorted(missing))}."
        )
