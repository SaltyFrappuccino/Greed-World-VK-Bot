import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import admin_ai as ai_crud
from bot.database.models import AdminAIPlan, AdminAISession
from bot.services import auth_service, character_service
from bot.services.admin_ai.sessions import _owned_session
from bot.services.admin_ai.normalizers import normalize_action_arguments
from bot.services.admin_ai.values import WRITE_TOOLS, _validate_action_arguments
from bot.services.admin_ai.write_tools import _action_snapshot, _execute_action
from bot.services.errors import PermissionDenied, ServiceError, ValidationError
from bot.utils.formatters import vk_plain_text

MAX_ACTIONS = 20
DESTRUCTIVE_TOOLS = {
    "character_delete",
    "card_delete",
    "contour_disassemble",
    "character_art_delete",
}


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
        arguments = normalize_action_arguments(name, arguments)
        action["arguments"] = arguments
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
) -> AdminAIPlan | None:
    auth_service.require_admin(admin_vk_id)
    plan = await ai_crud.get_plan_for_update(
        session, plan_id=plan_id, admin_vk_id=admin_vk_id
    )
    if plan is not None and plan.status != "executed":
        plan.status = "failed"
        plan.error = error[:2000]
        await session.flush()
    return plan


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
    elif "art_id" in arguments:
        target = dict(plan.snapshot.get(f"art:{arguments['art_id']}", {}))

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
        if key not in {"fields", "source_url"}
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
