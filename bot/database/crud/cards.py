from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Card, CardOwnership, CardType, Character, Rarity


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
    return await session.scalar(select(Card).where(Card.number == number))


async def search_by_name(session: AsyncSession, query: str, limit: int = 10) -> list[Card]:
    """Поиск по подстроке в названии, регистронезависимый."""
    expected = query.strip().casefold()
    cards = await session.scalars(select(Card).order_by(Card.name))
    return [card for card in cards if expected in card.name.casefold()][:limit]


async def list_cards(session: AsyncSession, offset: int = 0, limit: int = 10) -> list[Card]:
    stmt = select(Card).order_by(Card.name).offset(offset).limit(limit)
    return list(await session.scalars(stmt))


async def count_cards(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(Card)) or 0


async def create(
    session: AsyncSession,
    *,
    name: str,
    card_type: CardType,
    kind: str,
    rarity: Rarity,
    created_by: int,
    number: int | None = None,
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
    return await session.scalar(stmt)


async def add_ownership(session: AsyncSession, card_id: int, character_id: int) -> CardOwnership:
    ownership = CardOwnership(card_id=card_id, character_id=character_id)
    session.add(ownership)
    await session.flush()
    return ownership


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


async def list_card_owners(session: AsyncSession, card_id: int) -> list[Character]:
    stmt = (
        select(Character)
        .join(CardOwnership, CardOwnership.character_id == Character.id)
        .where(CardOwnership.card_id == card_id)
        .order_by(Character.name)
    )
    return list(await session.scalars(stmt))
