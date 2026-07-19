from vkbottle import DocMessagesUploader, Keyboard, KeyboardButtonColor, Text
from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

import json

from bot.database.engine import get_session
from bot.middlewares.auth import AdminRule, NotAdminRule
from bot.keyboards.main_menu import cancel, main_menu
from bot.services import admin_ai_assistant_service as assistant_service, vk_service
from bot.config import get_settings
from bot.services.errors import ServiceError
from bot.states import AdminAssistantState, clear_state, state_dispenser
from bot.utils.messages import answer_long
from bot.utils.photos import upload_message_photo
from bot.utils.validators import extract_vk_profile_urls
import logging

logger = logging.getLogger("zhadny_mir.chat_assistant")
try:
    logger.info("assistant.configured.admins=%s", get_settings().admin_vk_ids)
except Exception:
    logger.exception("failed to read configured admin ids")

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=True), AdminRule()])
labeler.vbml_ignore_case = True

# A public labeler to catch non-admin attempts and provide a clear reply.
public_labeler = BotLabeler(auto_rules=[PeerRule(from_chat=True), NotAdminRule()])
public_labeler.vbml_ignore_case = True


@public_labeler.message(text=["?ассистент", "?ассистент <query>"])
async def assistant_requires_admin(message: Message, **_: object) -> None:
    await message.answer("Требуются права администратора.")


@public_labeler.message(text=["?ассистент выход", "?ассистент закрыть"])
async def assistant_requires_admin_exit(message: Message, **_: object) -> None:
    await message.answer("Требуются права администратора.")


@labeler.message(text="?ассистент")
async def start_assistant(message: Message, **_: object) -> None:
    # extra runtime check (labeler already restricts via AdminRule)
    if not await AdminRule().check(message):
        await message.answer("Требуются права администратора.")
        return
    async with get_session() as session:
        ai_session = await assistant_service.open_session(
            session, admin_vk_id=message.from_id, peer_id=message.peer_id
        )
    await state_dispenser.set(message.peer_id, AdminAssistantState.CHAT, session_id=ai_session.id)
    logger.info("assistant.session.started peer=%s admin=%s session=%s", message.peer_id, message.from_id, ai_session.id)
    await message.answer(
        "Ассистент запущен в чате. Пиши запросы прямо сюда. Чтобы выйти — '?ассистент выход'.",
    )


@labeler.message(text=["?ассистент выход", "?ассистент закрыть"])
async def stop_assistant(message: Message, **_: object) -> None:
    if not await AdminRule().check(message):
        await message.answer("Требуются права администратора.")
        return
    try:
        async with get_session() as session:
            await assistant_service.close_session(
                session, session_id=int((await state_dispenser.get(message.peer_id)).payload.get("session_id", 0)), admin_vk_id=message.from_id, peer_id=message.peer_id
            )
    except Exception:
        pass
    await clear_state(message.peer_id)
    await message.answer("Ассистент остановлен.")


@labeler.message(text="?ассистент <query>")
async def start_assistant_with_query(message: Message, query: str, **_: object) -> None:
    # Start a session and immediately process the provided query text.
    if not get_settings().is_admin(message.from_id):
        await message.answer("Требуются права администратора.")
        return
    async with get_session() as session:
        ai_session = await assistant_service.open_session(
            session, admin_vk_id=message.from_id, peer_id=message.peer_id
        )
    await state_dispenser.set(message.peer_id, AdminAssistantState.CHAT, session_id=ai_session.id)
    # Inform user briefly and process the query
    await message.answer("Ассистент запущен. Обрабатываю запрос…")
    session_state = await state_dispenser.get(message.peer_id)
    session_id = int(session_state.payload.get("session_id", 0))
    logger.info("assistant.immediate.start peer=%s admin=%s session=%s query_len=%s", message.peer_id, message.from_id, ai_session.id, len(query))
    try:
        async with get_session() as session:
            outcome = await assistant_service.process_message(
                session,
                session_id=session_id,
                admin_vk_id=message.from_id,
                peer_id=message.peer_id,
                text=query,
                image_urls=_photo_urls(message),
                trusted_context=await _resolved_vk_context(message),
            )
            attachments = await _upload_attachments(message, outcome.attachments)
    except ServiceError as error:
        logger.warning("assistant.immediate.error peer=%s admin=%s error=%s", message.peer_id, message.from_id, error, exc_info=True)
        await message.answer(str(error))
        return
    except Exception:
        logger.exception("assistant.immediate.unhandled peer=%s admin=%s", message.peer_id, message.from_id)
        await message.answer("Ассистент не смог обработать запрос.")
        return

    if outcome.plan is not None:
        await state_dispenser.set(
            message.peer_id, AdminAssistantState.PLAN_CONFIRM, session_id=session_id, plan_id=outcome.plan.id
        )
        logger.info("assistant.immediate.plan peer=%s admin=%s plan_id=%s", message.peer_id, message.from_id, outcome.plan.id)
        await answer_long(
            message,
            assistant_service.format_plan(outcome.plan),
            keyboard=_plan_confirmation_keyboard(outcome.plan.id),
        )
        return

    logger.info("assistant.immediate.done peer=%s admin=%s resp_len=%s attachments=%s", message.peer_id, message.from_id, len(outcome.text), len(attachments))
    await answer_long(message, outcome.text)
    for kind, attachment, filename in attachments:
        title = "Основной арт персонажа." if kind == "photo" else f"Файл: {filename}"
        await message.answer(title, attachment=attachment)
    try:
        async with get_session() as session:
            await assistant_service.close_session(
                session,
                session_id=int((await state_dispenser.get(message.peer_id)).payload.get("session_id", 0)),
                admin_vk_id=message.from_id,
                peer_id=message.peer_id,
            )
    except Exception:
        pass
    await clear_state(message.peer_id)
    await message.answer("Ассистент остановлен.")


@labeler.message(payload_contains={"cmd": "chat_assistant_plan_confirm"})
async def confirm_chat_plan(message: Message, **_: object) -> None:
    if not await AdminRule().check(message):
        await message.answer("Требуются права администратора.")
        return
    payload = _parsed_payload(message.payload)
    plan_id = int(payload.get("plan_id", 0))
    if plan_id <= 0:
        await message.answer("Неверный идентификатор плана.")
        return
    await _confirm_chat_plan(message, destructive=False, plan_id=plan_id)


@labeler.message(payload_contains={"cmd": "chat_assistant_plan_destructive_confirm"})
async def confirm_chat_plan_destructive(message: Message, **_: object) -> None:
    if not await AdminRule().check(message):
        await message.answer("Требуются права администратора.")
        return
    payload = _parsed_payload(message.payload)
    plan_id = int(payload.get("plan_id", 0))
    if plan_id <= 0:
        await message.answer("Неверный идентификатор плана.")
        return
    await _confirm_chat_plan(message, destructive=True, plan_id=plan_id)


@labeler.message(text="?фиксменю")
async def fix_menu(message: Message, **_: object) -> None:
    if not await AdminRule().check(message):
        await message.answer("Требуются права администратора.")
        return
    await message.answer("Меню сброшено.", keyboard=Keyboard(one_time=False, inline=False).get_json())


def _parsed_payload(payload: str | dict[str, object] | None) -> dict[str, object]:
    if isinstance(payload, dict):
        return payload
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except Exception:
        logger.warning("assistant.chat.invalid_payload payload=%r", payload)
        return {}


@labeler.message(state=AdminAssistantState.CHAT)
async def chat(message: Message, **_: object) -> None:
    state = await state_dispenser.get(message.peer_id)
    if state is None:
        await message.answer("Сессия устарела. Запусти ?ассистент ещё раз.")
        return
    session_id = int(state.payload.get("session_id", 0))
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
        await message.answer(str(error))
        return
    except Exception:
        await message.answer("Ассистент не смог обработать запрос.")
        return

    if outcome.plan is not None:
        # If assistant returned a plan, keep state and add an inline confirmation button.
        await state_dispenser.set(message.peer_id, AdminAssistantState.PLAN_CONFIRM, session_id=session_id, plan_id=outcome.plan.id)
        await answer_long(
            message,
            assistant_service.format_plan(outcome.plan),
            keyboard=_plan_confirmation_keyboard(outcome.plan.id),
        )
        return

    await answer_long(message, outcome.text)
    for kind, attachment, filename in attachments:
        title = "Основной арт персонажа." if kind == "photo" else f"Файл: {filename}"
        await message.answer(title, attachment=attachment)


async def _confirm_chat_plan(message: Message, *, destructive: bool, plan_id: int) -> None:
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
        await message.answer(f"План не выполнен: {error}")
        return
    if not executed:
        await message.answer(
            "⚠ План содержит необратимое удаление. Нажми кнопку ниже, чтобы подтвердить удаление.",
            keyboard=_plan_destructive_confirmation_keyboard(plan.id),
        )
        return
    await message.answer("План подтверждён и выполнен.")


def _plan_confirmation_keyboard(plan_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=True)
    keyboard.add(
        Text("Подтвердить план", payload={"cmd": "chat_assistant_plan_confirm", "plan_id": plan_id}),
        color=KeyboardButtonColor.POSITIVE,
    )
    return keyboard.get_json()


def _plan_destructive_confirmation_keyboard(plan_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=True)
    keyboard.add(
        Text(
            "Подтвердить удаление",
            payload={"cmd": "chat_assistant_plan_destructive_confirm", "plan_id": plan_id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    return keyboard.get_json()


async def _upload_attachments(message: Message, items) -> list[tuple[str, str, str]]:
    result = []
    for item in items:
        if item.kind == "photo":
            attachment = await upload_message_photo(
                message.ctx_api, message.peer_id, item.data, filename=item.filename
            )
        else:
            uploader = DocMessagesUploader(message.ctx_api, attachment_name=item.filename)
            attachment = await uploader.upload(item.data, peer_id=message.peer_id, title=item.filename)
        result.append((item.kind, attachment, item.filename))
    return result


def _photo_urls(message: Message) -> list[str]:
    urls: list[str] = []
    for photo in message.get_photo_attachments() or []:
        sizes = [size for size in (photo.sizes or []) if size.url]
        original = getattr(photo, "orig_photo", None)
        if original is not None and original.url:
            sizes.append(original)
        if sizes:
            largest = max(sizes, key=lambda size: size.width * size.height)
            urls.append(largest.url)
        elif photo.photo_256:
            urls.append(photo.photo_256)
    return urls


async def _resolved_vk_context(message: Message) -> str:
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
        "Проверенные ботом через VK API ссылки из текущей просьбы. Используй только указанный числовой VK ID в изменяющих действиях:\n"
        + "\n".join(lines)
    )
