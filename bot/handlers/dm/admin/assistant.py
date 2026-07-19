import logging

from vkbottle import DocMessagesUploader
from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import admin_ai as ai_crud
from bot.database.engine import get_session
from bot.utils.photos import upload_message_photo
from bot.keyboards.admin_menu import (
    admin_ai_assistant_menu,
    admin_ai_destructive_menu,
    admin_ai_plan_menu,
    admin_menu,
)
from bot.middlewares.auth import AdminRule
from bot.services import admin_ai_assistant_service as assistant_service
from bot.services import vk_service
from bot.services.errors import ServiceError
from bot.states import AdminAssistantState, clear_state, state_dispenser
from bot.utils.messages import answer_long
from bot.utils.validators import extract_vk_profile_urls

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True
logger = logging.getLogger("zhadny_mir.ai_agent.handler")


@labeler.message(payload={"cmd": "admin_ai_assistant"})
async def enter_assistant(message: Message, **_: object) -> None:
    async with get_session() as session:
        ai_session = await assistant_service.open_session(
            session, admin_vk_id=message.from_id, peer_id=message.peer_id
        )
    await state_dispenser.set(
        message.peer_id, AdminAssistantState.CHAT, session_id=ai_session.id
    )
    await message.answer(
        "AI-Ассистент администратора активен. Опишите задачу свободным текстом. "
        "Он может изучать данные сразу, но любое изменение сначала покажет план и "
        "дождётся подтверждения.",
        keyboard=admin_ai_assistant_menu(ai_session.id),
    )


@labeler.message(payload_contains={"cmd": "admin_ai_assistant_new"})
async def new_task(message: Message, **_: object) -> None:
    session_id = _payload_id(message, "session_id")
    try:
        async with get_session() as session:
            ai_session = await assistant_service.start_new_session(
                session,
                session_id=session_id,
                admin_vk_id=message.from_id,
                peer_id=message.peer_id,
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=admin_menu())
        return
    await state_dispenser.set(
        message.peer_id, AdminAssistantState.CHAT, session_id=ai_session.id
    )
    await message.answer(
        "Начата новая задача с чистым контекстом. Предыдущий неподтверждённый план отменён.",
        keyboard=admin_ai_assistant_menu(ai_session.id),
    )


@labeler.message(payload_contains={"cmd": "admin_ai_assistant_history"})
async def show_history(message: Message, **_: object) -> None:
    session_id = _payload_id(message, "session_id")
    try:
        async with get_session() as session:
            text = await assistant_service.history_text(
                session, session_id=session_id, admin_vk_id=message.from_id, peer_id=message.peer_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=admin_menu())
        return
    await answer_long(message, text, keyboard=admin_ai_assistant_menu(session_id))


@labeler.message(payload_contains={"cmd": "admin_ai_assistant_plan"})
async def show_current_plan(message: Message, **_: object) -> None:
    session_id = _payload_id(message, "session_id")
    async with get_session() as session:
        try:
            await assistant_service.history_text(
                session, session_id=session_id, admin_vk_id=message.from_id, peer_id=message.peer_id
            )
            plan = await ai_crud.get_latest_plan(session, session_id=session_id)
        except ServiceError as error:
            await message.answer(str(error), keyboard=admin_menu())
            return
    if plan is None:
        await message.answer("В этой сессии ещё нет планов.", keyboard=admin_ai_assistant_menu(session_id))
        return
    if plan.status == "executed":
        await answer_long(
            message,
            assistant_service.format_result(plan),
            keyboard=admin_ai_assistant_menu(session_id),
        )
        return
    keyboard = (
        admin_ai_plan_menu(plan.id)
        if plan.status in {"proposed", "awaiting_destructive_confirmation"}
        else admin_ai_assistant_menu(session_id)
    )
    await answer_long(message, assistant_service.format_plan(plan), keyboard=keyboard)


@labeler.message(payload_contains={"cmd": "admin_ai_assistant_exit"})
async def exit_assistant(message: Message, **_: object) -> None:
    session_id = _payload_id(message, "session_id")
    try:
        async with get_session() as session:
            await assistant_service.close_session(
                session, session_id=session_id, admin_vk_id=message.from_id, peer_id=message.peer_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=admin_menu())
        return
    await clear_state(message.peer_id)
    await message.answer("AI-режим закрыт. Возвращаю в админ-панель.", keyboard=admin_menu())


@labeler.message(payload_contains={"cmd": "admin_ai_plan_confirm"})
async def confirm_plan(message: Message, **_: object) -> None:
    await _confirm(message, destructive=False)


@labeler.message(payload_contains={"cmd": "admin_ai_plan_destructive_confirm"})
async def confirm_destructive_plan(message: Message, **_: object) -> None:
    await _confirm(message, destructive=True)


async def _confirm(message: Message, *, destructive: bool) -> None:
    plan_id = _payload_id(message, "plan_id")
    current_state = message.state_peer
    previous_session_id = int(
        (current_state.payload if current_state is not None else {}).get("session_id", 0)
    )
    logger.info(
        "plan.confirm.start plan_id=%s admin_vk_id=%s peer_id=%s destructive=%s",
        plan_id,
        message.from_id,
        message.peer_id,
        destructive,
    )
    await state_dispenser.set(
        message.peer_id,
        AdminAssistantState.EXECUTING,
        plan_id=plan_id,
        session_id=previous_session_id,
    )
    try:
        async with get_session() as session:
            plan, executed = await assistant_service.confirm_plan(
                session,
                plan_id=plan_id,
                admin_vk_id=message.from_id,
                peer_id=message.peer_id,
                destructive_confirmed=destructive,
            )
    except ServiceError as error:
        logger.warning(
            "plan.confirm.failed plan_id=%s admin_vk_id=%s error_type=%s error=%s",
            plan_id,
            message.from_id,
            type(error).__name__,
            error,
            exc_info=True,
        )
        failed_plan = None
        try:
            async with get_session() as session:
                failed_plan = await assistant_service.mark_plan_failed(
                    session,
                    plan_id=plan_id,
                    admin_vk_id=message.from_id,
                    error=str(error),
                )
        except ServiceError:
            pass
        session_id = (
            failed_plan.session_id
            if failed_plan is not None
            else previous_session_id
        )
        if session_id > 0:
            await state_dispenser.set(
                message.peer_id,
                AdminAssistantState.CHAT,
                session_id=session_id,
            )
            keyboard = admin_ai_assistant_menu(session_id)
            suffix = "\n\nВы остались в AI-Ассистенте. Можно исправить просьбу и продолжить."
        else:
            await clear_state(message.peer_id)
            keyboard = admin_menu()
            suffix = ""
        await message.answer(f"План не выполнен: {error}{suffix}", keyboard=keyboard)
        return
    if not executed:
        logger.info("plan.confirm.awaiting_destructive plan_id=%s", plan.id)
        await state_dispenser.set(
            message.peer_id,
            AdminAssistantState.DESTRUCTIVE_CONFIRM,
            session_id=plan.session_id,
            plan_id=plan.id,
        )
        await message.answer(
            "⚠ План содержит необратимое удаление. Проверьте план ещё раз и подтвердите удаление отдельно.",
            keyboard=admin_ai_destructive_menu(plan.id),
        )
        return
    logger.info("plan.confirm.done plan_id=%s session_id=%s", plan.id, plan.session_id)
    await state_dispenser.set(
        message.peer_id, AdminAssistantState.CHAT, session_id=plan.session_id
    )
    await answer_long(
        message,
        assistant_service.format_result(plan),
        keyboard=admin_ai_assistant_menu(plan.session_id),
    )


@labeler.message(payload_contains={"cmd": "admin_ai_plan_cancel"})
async def cancel_plan(message: Message, **_: object) -> None:
    plan_id = _payload_id(message, "plan_id")
    try:
        async with get_session() as session:
            plan = await assistant_service.cancel_plan(
                session, plan_id=plan_id, admin_vk_id=message.from_id, peer_id=message.peer_id
            )
    except ServiceError as error:
        await message.answer(str(error), keyboard=admin_menu())
        return
    await state_dispenser.set(message.peer_id, AdminAssistantState.CHAT, session_id=plan.session_id)
    await message.answer("План отменён. Можно дать следующую задачу.", keyboard=admin_ai_assistant_menu(plan.session_id))


@labeler.message(payload_contains={"cmd": "admin_ai_plan_revise"})
async def revise_plan(message: Message, **_: object) -> None:
    await cancel_plan(message)


@labeler.message(state=AdminAssistantState.CHAT)
@labeler.message(state=AdminAssistantState.PLAN_CONFIRM)
@labeler.message(state=AdminAssistantState.DESTRUCTIVE_CONFIRM)
async def chat(message: Message, **_: object) -> None:
    state = message.state_peer
    session_id = int(state.payload["session_id"])
    pending_plan_id = state.payload.get("plan_id")
    logger.info(
        "chat.received session_id=%s admin_vk_id=%s peer_id=%s text_chars=%s images=%s "
        "pending_plan_id=%s",
        session_id,
        message.from_id,
        message.peer_id,
        len(message.text or ""),
        len(message.get_photo_attachments() or []),
        pending_plan_id,
    )
    if pending_plan_id is not None:
        try:
            async with get_session() as session:
                await assistant_service.cancel_plan(
                    session,
                    plan_id=int(pending_plan_id),
                    admin_vk_id=message.from_id,
                    peer_id=message.peer_id,
                )
        except ServiceError:
            pass
        await state_dispenser.set(
            message.peer_id, AdminAssistantState.CHAT, session_id=session_id
        )
    try:
        async with get_session() as session:
            outcome = await assistant_service.process_message(
                session,
                session_id=session_id,
                admin_vk_id=message.from_id,
                peer_id=message.peer_id,
                text=message.text,
                image_urls=_photo_urls(message),
                trusted_context=await _resolved_vk_context(message),
            )
        attachments = await _upload_attachments(message, outcome.attachments)
    except ServiceError as error:
        logger.warning(
            "chat.service_error session_id=%s admin_vk_id=%s error_type=%s error=%s",
            session_id,
            message.from_id,
            type(error).__name__,
            error,
            exc_info=True,
        )
        await message.answer(str(error), keyboard=admin_ai_assistant_menu(session_id))
        return
    except Exception:
        logger.exception("Ошибка AI-Ассистента администратора")
        await message.answer("AI-Ассистент не смог завершить запрос. Данные не изменены.", keyboard=admin_ai_assistant_menu(session_id))
        return
    if outcome.plan is not None:
        await state_dispenser.set(
            message.peer_id,
            AdminAssistantState.PLAN_CONFIRM,
            session_id=session_id,
            plan_id=outcome.plan.id,
        )
        keyboard = admin_ai_plan_menu(outcome.plan.id)
    else:
        keyboard = admin_ai_assistant_menu(session_id)
    logger.info(
        "chat.respond session_id=%s admin_vk_id=%s response_chars=%s plan_id=%s attachments=%s",
        session_id,
        message.from_id,
        len(outcome.text),
        getattr(outcome.plan, "id", None),
        len(attachments),
    )
    await answer_long(message, outcome.text, keyboard=keyboard)
    for kind, attachment, filename in attachments:
        title = "Основной арт персонажа." if kind == "photo" else f"Файл AI-Ассистента готов: {filename}"
        await message.answer(title, attachment=attachment, keyboard=keyboard)


async def _upload_attachments(
    message: Message, items
) -> list[tuple[str, str, str]]:
    result = []
    for item in items:
        if item.kind == "photo":
            attachment = await upload_message_photo(
                message.ctx_api,
                message.peer_id,
                item.data,
                filename=item.filename,
            )
        else:
            uploader = DocMessagesUploader(message.ctx_api, attachment_name=item.filename)
            attachment = await uploader.upload(
                item.data, peer_id=message.peer_id, title=item.filename
            )
        result.append((item.kind, attachment, item.filename))
    return result


def _payload_id(message: Message, key: str) -> int:
    payload = message.get_payload_json() or {}
    try:
        value = int(payload[key])
    except (KeyError, TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _photo_urls(message: Message) -> list[str]:
    urls = []
    for photo in message.get_photo_attachments() or []:
        sizes = [size for size in (photo.sizes or []) if size.url]
        original = getattr(photo, "orig_photo", None)
        if original is not None and original.url:
            sizes.append(original)
        if sizes:
            urls.append(max(sizes, key=lambda size: size.width * size.height).url)
        elif photo.photo_256:
            urls.append(photo.photo_256)
    return urls


async def _resolved_vk_context(message: Message) -> str:
    """Разрешить изменяемые короткие адреса VK в стабильные числовые ID."""
    lines: list[str] = []
    for reference in extract_vk_profile_urls(message.text or ""):
        try:
            vk_id = await vk_service.resolve_user_id(message.ctx_api, reference)
        except ServiceError as error:
            lines.append(f"• {reference}: не удалось разрешить ({error})")
        else:
            lines.append(f"• {reference} → числовой VK ID {vk_id}")
    if not lines:
        return ""
    return (
        "Проверенные ботом через VK API ссылки из текущей просьбы. "
        "Используй только указанный числовой VK ID в изменяющих действиях:\n"
        + "\n".join(lines)
    )
