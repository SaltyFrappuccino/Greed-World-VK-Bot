from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import AdminAIMessage, AdminAIPlan, AdminAISession


async def get_or_create_session(
    session: AsyncSession, *, admin_vk_id: int, peer_id: int
) -> AdminAISession:
    stmt = (
        select(AdminAISession)
        .where(
            AdminAISession.admin_vk_id == admin_vk_id,
            AdminAISession.peer_id == peer_id,
            AdminAISession.status == "active",
        )
        .order_by(AdminAISession.id.desc())
        .limit(1)
    )
    existing = await session.scalar(stmt)
    if existing is not None:
        return existing
    result = AdminAISession(admin_vk_id=admin_vk_id, peer_id=peer_id, status="active")
    session.add(result)
    await session.flush()
    return result


async def get_owned_session(
    session: AsyncSession, *, session_id: int, admin_vk_id: int, peer_id: int
) -> AdminAISession | None:
    stmt = select(AdminAISession).where(
        AdminAISession.id == session_id,
        AdminAISession.admin_vk_id == admin_vk_id,
        AdminAISession.peer_id == peer_id,
    )
    return await session.scalar(stmt)


async def close_session(session: AsyncSession, item: AdminAISession) -> None:
    item.status = "closed"
    item.closed_at = datetime.now(timezone.utc)
    await session.flush()


async def add_message(
    session: AsyncSession,
    *,
    session_id: int,
    role: str,
    content: str,
    details: dict[str, object] | None = None,
) -> AdminAIMessage:
    item = AdminAIMessage(
        session_id=session_id,
        role=role,
        content=content,
        details=details or {},
    )
    session.add(item)
    await session.flush()
    return item


async def list_messages(
    session: AsyncSession, session_id: int, *, limit: int = 30
) -> list[AdminAIMessage]:
    stmt = (
        select(AdminAIMessage)
        .where(AdminAIMessage.session_id == session_id)
        .order_by(AdminAIMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(list(await session.scalars(stmt))))


async def list_admin_messages(
    session: AsyncSession, *, admin_vk_id: int, peer_id: int, limit: int = 30
) -> list[AdminAIMessage]:
    stmt = (
        select(AdminAIMessage)
        .join(AdminAISession, AdminAISession.id == AdminAIMessage.session_id)
        .where(
            AdminAISession.admin_vk_id == admin_vk_id,
            AdminAISession.peer_id == peer_id,
        )
        .order_by(AdminAIMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(list(await session.scalars(stmt))))


async def create_plan(
    session: AsyncSession,
    *,
    session_id: int,
    admin_vk_id: int,
    summary: str,
    actions: list[dict[str, object]],
    snapshot: dict[str, object],
    warnings: list[str],
    destructive: bool,
) -> AdminAIPlan:
    await supersede_open_plans(session, session_id)
    plan = AdminAIPlan(
        session_id=session_id,
        admin_vk_id=admin_vk_id,
        summary=summary,
        actions=actions,
        snapshot=snapshot,
        warnings=warnings,
        destructive=destructive,
    )
    session.add(plan)
    await session.flush()
    return plan


async def supersede_open_plans(session: AsyncSession, session_id: int) -> None:
    stmt = select(AdminAIPlan).where(
        AdminAIPlan.session_id == session_id,
        AdminAIPlan.status.in_(("proposed", "awaiting_destructive_confirmation")),
    )
    for plan in await session.scalars(stmt):
        plan.status = "superseded"
    await session.flush()


async def get_plan_for_update(
    session: AsyncSession, *, plan_id: int, admin_vk_id: int
) -> AdminAIPlan | None:
    stmt = (
        select(AdminAIPlan)
        .where(AdminAIPlan.id == plan_id, AdminAIPlan.admin_vk_id == admin_vk_id)
        .with_for_update()
    )
    return await session.scalar(stmt)


async def get_latest_plan(
    session: AsyncSession, *, session_id: int
) -> AdminAIPlan | None:
    stmt = (
        select(AdminAIPlan)
        .where(AdminAIPlan.session_id == session_id)
        .order_by(AdminAIPlan.id.desc())
        .limit(1)
    )
    return await session.scalar(stmt)
