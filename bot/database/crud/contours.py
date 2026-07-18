from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import CardOwnership, Contour, ContourComponent


def _with_components():
    return selectinload(Contour.components).selectinload(
        ContourComponent.ownership
    ).selectinload(CardOwnership.card)


async def list_for_character(
    session: AsyncSession, character_id: int
) -> list[Contour]:
    stmt = (
        select(Contour)
        .where(Contour.character_id == character_id)
        .options(_with_components())
        .execution_options(populate_existing=True)
        .order_by(Contour.slot)
    )
    return list(await session.scalars(stmt))


async def get_by_id(session: AsyncSession, contour_id: int) -> Contour | None:
    stmt = (
        select(Contour)
        .where(Contour.id == contour_id)
        .options(_with_components())
        .execution_options(populate_existing=True)
    )
    return await session.scalar(stmt)


async def get_by_id_for_update(
    session: AsyncSession, contour_id: int
) -> Contour | None:
    stmt = (
        select(Contour)
        .where(Contour.id == contour_id)
        .options(_with_components())
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    return await session.scalar(stmt)


async def create(
    session: AsyncSession,
    *,
    character_id: int,
    slot: int,
    name: str,
    created_by: int,
    **fields: object,
) -> Contour:
    contour = Contour(
        character_id=character_id,
        slot=slot,
        name=name.strip(),
        created_by=created_by,
        **fields,
    )
    session.add(contour)
    await session.flush()
    return contour


async def update(session: AsyncSession, contour: Contour, **fields: object) -> Contour:
    for key, value in fields.items():
        if not hasattr(contour, key):
            raise AttributeError(f"У Контура нет поля {key!r}")
        setattr(contour, key, value)
    await session.flush()
    return contour


async def add_component(
    session: AsyncSession,
    *,
    contour_id: int,
    ownership_id: int,
    position: int,
) -> ContourComponent:
    component = ContourComponent(
        contour_id=contour_id,
        card_ownership_id=ownership_id,
        position=position,
    )
    session.add(component)
    await session.flush()
    return component


async def get_component(
    session: AsyncSession, component_id: int
) -> ContourComponent | None:
    stmt = (
        select(ContourComponent)
        .where(ContourComponent.id == component_id)
        .options(
            selectinload(ContourComponent.contour),
            selectinload(ContourComponent.ownership).selectinload(
                CardOwnership.card
            ),
        )
    )
    return await session.scalar(stmt)


async def delete_component(
    session: AsyncSession, component: ContourComponent
) -> None:
    await session.delete(component)
    await session.flush()


async def delete(session: AsyncSession, contour: Contour) -> None:
    await session.delete(contour)
    await session.flush()
