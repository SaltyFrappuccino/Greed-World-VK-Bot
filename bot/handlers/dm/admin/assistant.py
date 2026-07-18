import logging

from vkbottle import DocMessagesUploader
from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.crud import admin_ai as ai_crud
from bot.database.engine import get_session
from bot.keyboards.admin_menu import (
    admin_ai_assistant_menu,
    admin_ai_destructive_menu,
    admin_ai_plan_menu,
    admin_menu,
)
from bot.middlewares.auth import AdminRule
from bot.services import admin_ai_assistant_service as assistant_service
from bot.services.errors import ServiceError
from bot.states import AdminAssistantState, clear_state, state_dispenser
from bot.utils.messages import answer_long

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True
logger = logging.getLogger(__name__)


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
    await state_dispenser.set(message.peer_id, AdminAssistantState.EXECUTING, plan_id=plan_id)
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
        try:
            async with get_session() as session:
                await assistant_service.mark_plan_failed(
                    session,
                    plan_id=plan_id,
                    admin_vk_id=message.from_id,
                    error=str(error),
                )
        except ServiceError:
            pass
        await message.answer(str(error), keyboard=admin_menu())
        return
    if not executed:
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
            )
        attachments = await _upload_attachments(message, outcome.attachments)
    except ServiceError as error:
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
    await answer_long(message, outcome.text, keyboard=keyboard)
    for attachment in attachments:
        await message.answer("Файл AI-Ассистента готов.", attachment=attachment, keyboard=keyboard)


async def _upload_attachments(message: Message, items) -> list[str]:
    result = []
    for item in items:
        uploader = DocMessagesUploader(message.ctx_api, attachment_name=item.filename)
        result.append(await uploader.upload(item.data, peer_id=message.peer_id, title=item.filename))
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
