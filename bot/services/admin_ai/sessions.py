from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import admin_ai as ai_crud
from bot.database.models import AdminAISession
from bot.services import auth_service
from bot.services.errors import PermissionDenied
from bot.utils.formatters import vk_plain_text


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

