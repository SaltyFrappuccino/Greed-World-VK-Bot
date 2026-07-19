import json
import logging
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import admin_ai as ai_crud
from bot.services import ai_service, auth_service
from bot.services.admin_ai.planning import create_plan, format_plan
from bot.services.admin_ai.diagnostics import (
    elapsed_ms,
    new_request_id,
    result_summary,
    safe_json,
)
from bot.services.admin_ai.policy import _clarification_policy_error
from bot.services.admin_ai.read_tools import _failed_read_observation, _run_read_tool
from bot.services.admin_ai.runtime import AssistantAttachment, AssistantOutcome
from bot.services.admin_ai.sessions import _model_history, _owned_session
from bot.services.errors import ServiceError, ValidationError
from bot.utils.formatters import vk_plain_text

MAX_TOOL_ROUNDS = 10
MAX_IDENTICAL_PLAN_REJECTIONS = 2
logger = logging.getLogger("zhadny_mir.ai_agent")


async def process_message(
    session: AsyncSession,
    *,
    session_id: int,
    admin_vk_id: int,
    peer_id: int,
    text: str,
    image_urls: list[str] | None = None,
    trusted_context: str = "",
) -> AssistantOutcome:
    request_id = new_request_id()
    started_at = perf_counter()
    logger.info(
        "task.start request_id=%s session_id=%s admin_vk_id=%s peer_id=%s "
        "text_chars=%s images=%s",
        request_id,
        session_id,
        admin_vk_id,
        peer_id,
        len(text),
        len(image_urls or []),
    )
    try:
        outcome = await _process_message(
            session,
            session_id=session_id,
            admin_vk_id=admin_vk_id,
            peer_id=peer_id,
            text=text,
            image_urls=image_urls,
            trusted_context=trusted_context,
            request_id=request_id,
        )
    except Exception as error:
        logger.error(
            "task.failed request_id=%s session_id=%s duration_ms=%s error_type=%s error=%s",
            request_id,
            session_id,
            elapsed_ms(started_at),
            type(error).__name__,
            error,
            exc_info=True,
        )
        raise
    logger.info(
        "task.done request_id=%s session_id=%s duration_ms=%s response_chars=%s "
        "plan_id=%s attachments=%s",
        request_id,
        session_id,
        elapsed_ms(started_at),
        len(outcome.text),
        getattr(outcome.plan, "id", None),
        len(outcome.attachments),
    )
    return outcome


async def _process_message(
    session: AsyncSession,
    *,
    session_id: int,
    admin_vk_id: int,
    peer_id: int,
    text: str,
    image_urls: list[str] | None,
    trusted_context: str,
    request_id: str,
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
        details={"image_count": len(image_urls or []), "request_id": request_id},
    )
    if trusted_context.strip():
        await ai_crud.add_message(
            session,
            session_id=ai_session.id,
            role="tool",
            content=trusted_context.strip(),
            details={"trusted_vk_context": True, "request_id": request_id},
        )

    attachments: list[AssistantAttachment] = []
    plan_rejections: dict[str, int] = {}
    for round_number in range(MAX_TOOL_ROUNDS):
        history = await _model_history(session, ai_session.id)
        logger.info(
            "round.start request_id=%s round=%s history_messages=%s history_chars=%s",
            request_id,
            round_number + 1,
            len(history),
            sum(len(item["content"]) for item in history),
        )
        turn = await ai_service.generate_admin_assistant_turn(
            history,
            # Текущие изображения должны оставаться видимыми модели и после
            # read-инструмента либо отклонённого плана.
            image_urls=image_urls,
            request_id=request_id,
            round_number=round_number + 1,
        )
        logger.info(
            "round.turn request_id=%s round=%s kind=%s tools=%s actions=%s warnings=%s",
            request_id,
            round_number + 1,
            turn.kind,
            len(turn.tools),
            len(turn.actions),
            len(turn.warnings),
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
                    details={
                        "clarification_rejected": True,
                        "request_id": request_id,
                    },
                )
                logger.warning(
                    "clarification.rejected request_id=%s round=%s reason=%s",
                    request_id,
                    round_number + 1,
                    policy_error,
                )
                continue
        if turn.kind in {"answer", "clarification"}:
            response_text = vk_plain_text(turn.message)
            await ai_crud.add_message(
                session,
                session_id=ai_session.id,
                role="assistant",
                content=response_text,
                details={"request_id": request_id},
            )
            return AssistantOutcome(response_text, attachments=tuple(attachments))
        if turn.kind == "read_tools":
            if not turn.tools:
                raise ValidationError("AI запросил чтение, но не указал инструменты.")
            results = []
            for tool in turn.tools:
                tool_started_at = perf_counter()
                logger.info(
                    "tool.start request_id=%s round=%s tool=%s arguments=%s",
                    request_id,
                    round_number + 1,
                    tool.name,
                    safe_json(tool.arguments),
                )
                try:
                    result, attachment = await _run_read_tool(
                        session, tool.name, tool.arguments
                    )
                    observation = {"tool": tool.name, "ok": True, "result": result}
                    logger.info(
                        "tool.done request_id=%s round=%s tool=%s duration_ms=%s result=%s attachment=%s",
                        request_id,
                        round_number + 1,
                        tool.name,
                        elapsed_ms(tool_started_at),
                        result_summary(result),
                        attachment.filename if attachment is not None else None,
                    )
                except ServiceError as error:
                    attachment = None
                    observation = await _failed_read_observation(
                        session, tool.name, tool.arguments, error
                    )
                    logger.warning(
                        "tool.failed request_id=%s round=%s tool=%s duration_ms=%s "
                        "error_type=%s error=%s observation=%s",
                        request_id,
                        round_number + 1,
                        tool.name,
                        elapsed_ms(tool_started_at),
                        type(error).__name__,
                        error,
                        safe_json(observation),
                    )
                results.append(observation)
                if attachment is not None and not any(
                    item.kind == attachment.kind
                    and item.filename == attachment.filename
                    for item in attachments
                ):
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
                details={"results": results, "request_id": request_id},
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
            try:
                _resolve_art_image_actions(actions, image_urls or [])
                plan = await create_plan(
                    session,
                    ai_session=ai_session,
                    admin_vk_id=admin_vk_id,
                    summary=vk_plain_text(turn.message),
                    actions=actions,
                    warnings=[vk_plain_text(item) for item in turn.warnings],
                )
            except ServiceError as error:
                error_text = str(error)
                plan_rejections[error_text] = plan_rejections.get(error_text, 0) + 1
                logger.warning(
                    "plan.rejected request_id=%s round=%s error=%s",
                    request_id,
                    round_number + 1,
                    error,
                )
                if plan_rejections[error_text] >= MAX_IDENTICAL_PLAN_REJECTIONS:
                    raise ValidationError(
                        "AI дважды предложил один и тот же некорректный план. "
                        f"Данные не изменены. Ошибка плана: {error_text}"
                    ) from error
                await ai_crud.add_message(
                    session,
                    session_id=ai_session.id,
                    role="tool",
                    content=(
                        "ПЛАН ОТКЛОНЁН И НЕ ПОКАЗАН ПОЛЬЗОВАТЕЛЮ. "
                        "Никакие изменения не выполнены. Исправь только ошибочные "
                        "действия по диагностике ниже, не повторяй прежние аргументы "
                        "и верни новый полный action_plan. "
                        f"Диагностика: {error}"
                    ),
                    details={
                        "plan_rejected": True,
                        "request_id": request_id,
                        "error": str(error),
                    },
                )
                continue
            logger.info(
                "plan.proposed request_id=%s round=%s plan_id=%s actions=%s destructive=%s",
                request_id,
                round_number + 1,
                plan.id,
                len(actions),
                any(action["name"].endswith("delete") or action["name"] == "contour_disassemble" for action in actions),
            )
            await ai_crud.add_message(
                session,
                session_id=ai_session.id,
                role="assistant",
                content=format_plan(plan),
                details={"plan_id": plan.id, "request_id": request_id},
            )
            return AssistantOutcome(format_plan(plan), plan=plan, attachments=tuple(attachments))
    raise ValidationError(
        "AI не смог построить корректный ответ за допустимое число шагов. "
        "Данные не изменены."
    )


def _resolve_art_image_actions(
    actions: list[dict[str, object]], image_urls: list[str]
) -> None:
    def resolve(arguments: dict[str, object]) -> None:
        try:
            image_index = int(arguments.pop("image_index"))
            source_url = image_urls[image_index - 1]
        except (KeyError, TypeError, ValueError, IndexError) as error:
            raise ValidationError(
                "Для добавления арта укажите image_index приложенного к текущей просьбе изображения."
            ) from error
        arguments["source_url"] = source_url

    for action in actions:
        arguments = action.get("arguments")
        if not isinstance(arguments, dict):
            raise ValidationError("Некорректные аргументы добавления арта.")
        if action.get("name") == "character_art_add":
            resolve(arguments)
        elif action.get("name") == "character_create" and "arts" in arguments:
            arts = arguments["arts"]
            if not isinstance(arts, list):
                raise ValidationError("Поле arts новой анкеты должно быть списком.")
            for art in arts:
                if not isinstance(art, dict):
                    raise ValidationError("Каждый арт новой анкеты должен быть объектом.")
                resolve(art)
