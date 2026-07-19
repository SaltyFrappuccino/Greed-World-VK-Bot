from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import (
    Card,
    CardOwnership,
    CardType,
    Character,
    ContourComponent,
    Rarity,
)


async def get_by_id(session: AsyncSession, card_id: int) -> Card | None:
    return await session.get(Card, card_id)


async def get_by_id_for_update(session: AsyncSession, card_id: int) -> Card | None:
    stmt = select(Card).where(Card.id == card_id).with_for_update()
    return await session.scalar(stmt)


async def get_by_name(session: AsyncSession, name: str) -> Card | None:
    expected = name.strip().casefold()
    cards = await session.scalars(select(Card).order_by(Card.name))
    return next((card for card in cards if card.name.casefold() == expected), None)


async def get_by_number(session: AsyncSession, number: int) -> Card | None:
    return await session.scalar(
        select(Card).where(
            Card.card_type == CardType.SPECIAL,
            Card.number == number,
        )
    )


async def get_by_registry_number(session: AsyncSession, number: int) -> Card | None:
    return await session.scalar(
        select(Card).where(
            Card.card_type.in_((CardType.SPELL, CardType.CONTOUR)),
            Card.registry_number == number,
        )
    )


async def next_registry_number(session: AsyncSession) -> int:
    numbers = list(
        await session.scalars(
            select(Card.registry_number)
            .where(Card.registry_number.is_not(None))
            .order_by(Card.registry_number)
        )
    )
    expected = 0
    for number in numbers:
        if number == expected:
            expected += 1
        elif number is not None and number > expected:
            break
    return expected


async def search_by_name(session: AsyncSession, query: str, limit: int = 10) -> list[Card]:
    """Поиск по подстроке в названии, регистронезависимый."""
    expected = query.strip().casefold()
    cards = await session.scalars(select(Card).order_by(Card.name))
    return [card for card in cards if expected in card.name.casefold()][:limit]


async def list_cards(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 10,
    card_types: tuple[CardType, ...] | None = None,
) -> list[Card]:
    stmt = select(Card)
    if card_types:
        stmt = stmt.where(Card.card_type.in_(card_types))
    stmt = stmt.order_by(Card.card_type, Card.number, Card.registry_number, Card.name).offset(offset).limit(limit)
    return list(await session.scalars(stmt))


async def count_cards(
    session: AsyncSession, card_types: tuple[CardType, ...] | None = None
) -> int:
    stmt = select(func.count()).select_from(Card)
    if card_types:
        stmt = stmt.where(Card.card_type.in_(card_types))
    return await session.scalar(stmt) or 0


async def create(
    session: AsyncSession,
    *,
    name: str,
    card_type: CardType,
    kind: str,
    rarity: Rarity,
    created_by: int,
    number: int | None = None,
    registry_number: int | None = None,
    description: str = "",
    usage: str = "",
    transform_limit: int | None = None,
) -> Card:
    card = Card(
        name=name.strip(),
        card_type=card_type,
        kind=kind.strip(),
        rarity=rarity,
        created_by=created_by,
        number=number,
        registry_number=registry_number,
        description=description,
        usage=usage,
        transform_limit=transform_limit,
    )
    session.add(card)
    await session.flush()
    return card


async def update(session: AsyncSession, card: Card, **fields: object) -> Card:
    for key, value in fields.items():
        if not hasattr(card, key):
            raise AttributeError(f"У карты нет поля {key!r}")
        setattr(card, key, value)
    await session.flush()
    return card


async def delete(session: AsyncSession, card: Card) -> None:
    await session.delete(card)
    await session.flush()


async def count_owners(session: AsyncSession, card_id: int) -> int:
    """Реальное число живых копий по таблице владений."""
    stmt = select(func.count()).select_from(CardOwnership).where(CardOwnership.card_id == card_id)
    return await session.scalar(stmt) or 0


async def get_ownership(
    session: AsyncSession, card_id: int, character_id: int
) -> CardOwnership | None:
    stmt = select(CardOwnership).where(
        CardOwnership.card_id == card_id,
        CardOwnership.character_id == character_id,
    )
    return await session.scalar(stmt.order_by(CardOwnership.id))


async def get_ownership_by_id(
    session: AsyncSession, ownership_id: int
) -> CardOwnership | None:
    stmt = (
        select(CardOwnership)
        .where(CardOwnership.id == ownership_id)
        .options(
            selectinload(CardOwnership.card),
            selectinload(CardOwnership.contour_component).selectinload(
                ContourComponent.contour
            ),
        )
    )
    return await session.scalar(stmt)


async def get_free_ownership(
    session: AsyncSession, card_id: int, character_id: int
) -> CardOwnership | None:
    items = await list_free_ownerships(session, card_id, character_id, limit=1)
    return items[0] if items else None


async def list_free_ownerships(
    session: AsyncSession,
    card_id: int,
    character_id: int,
    *,
    limit: int | None = None,
) -> list[CardOwnership]:
    stmt = (
        select(CardOwnership)
        .outerjoin(
            ContourComponent,
            ContourComponent.card_ownership_id == CardOwnership.id,
        )
        .where(
            CardOwnership.card_id == card_id,
            CardOwnership.character_id == character_id,
            ContourComponent.id.is_(None),
        )
        .order_by(CardOwnership.id)
        .with_for_update(of=CardOwnership)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(await session.scalars(stmt))


async def add_ownership(session: AsyncSession, card_id: int, character_id: int) -> CardOwnership:
    ownership = CardOwnership(card_id=card_id, character_id=character_id)
    session.add(ownership)
    await session.flush()
    return ownership


async def add_ordinary_ownership(
    session: AsyncSession,
    *,
    character_id: int,
    name: str,
    kind: str,
    rarity: Rarity,
    description: str = "",
    usage: str = "",
) -> CardOwnership:
    ownership = CardOwnership(
        character_id=character_id,
        card_id=None,
        ordinary_name=name.strip(),
        ordinary_kind=kind.strip(),
        ordinary_rarity=rarity,
        ordinary_description=description.strip(),
        ordinary_usage=usage.strip(),
    )
    session.add(ownership)
    await session.flush()
    return ownership


async def get_free_ordinary_ownership(
    session: AsyncSession, character_id: int, name: str
) -> CardOwnership | None:
    items = await list_free_ordinary_ownerships(session, character_id, name, limit=1)
    return items[0] if items else None


async def list_free_ordinary_ownerships(
    session: AsyncSession,
    character_id: int,
    name: str,
    *,
    limit: int | None = None,
) -> list[CardOwnership]:
    expected = name.strip().casefold()
    stmt = (
        select(CardOwnership)
        .outerjoin(
            ContourComponent,
            ContourComponent.card_ownership_id == CardOwnership.id,
        )
        .where(
            CardOwnership.character_id == character_id,
            CardOwnership.card_id.is_(None),
            ContourComponent.id.is_(None),
        )
        .order_by(CardOwnership.id)
        .with_for_update(of=CardOwnership)
    )
    ownerships = list(await session.scalars(stmt))
    matches = [
        ownership
        for ownership in ownerships
        if (ownership.ordinary_name or "").casefold() == expected
    ]
    return matches if limit is None else matches[:limit]


async def list_free_consumable_ownerships(
    session: AsyncSession, character_id: int, name: str
) -> list[CardOwnership]:
    """Free Spell or Ordinary copies matching an exact display name."""
    expected = name.strip().casefold()
    stmt = (
        select(CardOwnership)
        .outerjoin(
            ContourComponent,
            ContourComponent.card_ownership_id == CardOwnership.id,
        )
        .outerjoin(Card, Card.id == CardOwnership.card_id)
        .where(
            CardOwnership.character_id == character_id,
            ContourComponent.id.is_(None),
            (
                CardOwnership.card_id.is_(None)
                | (Card.card_type == CardType.SPELL)
            ),
        )
        .options(selectinload(CardOwnership.card))
        .order_by(CardOwnership.id)
        .with_for_update(of=CardOwnership)
    )
    items = list(await session.scalars(stmt))
    return [item for item in items if item.display_name.casefold() == expected]


async def remove_ownership(session: AsyncSession, ownership: CardOwnership) -> None:
    await session.delete(ownership)
    await session.flush()


async def list_character_cards(session: AsyncSession, character_id: int) -> list[Card]:
    stmt = (
        select(Card)
        .join(CardOwnership, CardOwnership.card_id == Card.id)
        .where(CardOwnership.character_id == character_id)
        .order_by(Card.name)
    )
    return list(await session.scalars(stmt))


async def list_character_ownerships(
    session: AsyncSession, character_id: int
) -> list[CardOwnership]:
    stmt = (
        select(CardOwnership)
        .where(CardOwnership.character_id == character_id)
        .outerjoin(Card, Card.id == CardOwnership.card_id)
        .options(
            selectinload(CardOwnership.card),
            selectinload(CardOwnership.contour_component).selectinload(
                ContourComponent.contour
            ),
        )
        .order_by(
            Card.card_type,
            Card.number,
            Card.registry_number,
            Card.name,
            CardOwnership.ordinary_name,
            CardOwnership.id,
        )
    )
    return list(await session.scalars(stmt))


async def list_card_ownerships(
    session: AsyncSession, card_id: int
) -> list[CardOwnership]:
    stmt = (
        select(CardOwnership)
        .where(CardOwnership.card_id == card_id)
        .join(Character, Character.id == CardOwnership.character_id)
        .options(
            selectinload(CardOwnership.character),
            selectinload(CardOwnership.contour_component).selectinload(
                ContourComponent.contour
            ),
        )
        .order_by(Character.name, CardOwnership.id)
    )
    return list(await session.scalars(stmt))


async def count_bound_ownerships(session: AsyncSession, card_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(ContourComponent)
        .join(
            CardOwnership,
            CardOwnership.id == ContourComponent.card_ownership_id,
        )
        .where(CardOwnership.card_id == card_id)
    )
    return await session.scalar(stmt) or 0


async def list_card_owners(session: AsyncSession, card_id: int) -> list[Character]:
    stmt = (
        select(Character)
        .join(CardOwnership, CardOwnership.character_id == Character.id)
        .where(CardOwnership.card_id == card_id)
        .order_by(Character.name)
        .distinct()
    )
    return list(await session.scalars(stmt))
