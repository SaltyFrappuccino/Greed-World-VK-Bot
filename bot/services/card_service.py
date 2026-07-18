from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import Card, CardOwnership, CardType, Rarity
from bot.services.errors import NotFoundError, TransformLimitReached, ValidationError


async def create_card(
    session: AsyncSession,
    *,
    name: str,
    card_type: CardType = CardType.ORDINARY,
    kind: str,
    rarity: Rarity,
    admin_vk_id: int,
    number: int | None = None,
    description: str = "",
    usage: str = "",
    transform_limit: int | None = None,
) -> Card:
    if not name.strip():
        raise ValidationError("Название карты не может быть пустым.")
    if not kind.strip():
        raise ValidationError("Вид карты не может быть пустым.")
    if card_type is CardType.ORDINARY:
        raise ValidationError(
            "Обычные карты не создаются в реестре — добавьте карту сразу персонажу."
        )
    if card_type is CardType.SPECIAL and number is None:
        raise ValidationError("Для Особой карты укажите номер слота от 0 до 99.")
    if number is not None and not 0 <= number <= 99:
        raise ValidationError("Номер Особого слота должен быть от 0 до 99.")
    if card_type is not CardType.SPECIAL and number is not None:
        raise ValidationError("Номер Особого слота допустим только для Особой карты.")
    if transform_limit is not None and transform_limit < 1:
        raise ValidationError("Лимит преобразований должен быть больше нуля (или не задан вовсе).")
    if card_type is not CardType.SPECIAL and transform_limit is not None:
        raise ValidationError("Лимит преобразований задаётся только Особым картам.")

    if await cards_crud.get_by_name(session, name) is not None:
        raise ValidationError(f"Карта «{name.strip()}» уже есть в реестре.")
    if number is not None and await cards_crud.get_by_number(session, number) is not None:
        raise ValidationError(f"Особый слот №{number} уже занят.")

    registry_number = None
    if card_type in (CardType.SPELL, CardType.CONTOUR):
        registry_number = await cards_crud.next_registry_number(session)

    return await cards_crud.create(
        session,
        name=name,
        card_type=card_type,
        kind=kind,
        rarity=rarity,
        created_by=admin_vk_id,
        number=number,
        registry_number=registry_number,
        description=description,
        usage=usage,
        transform_limit=transform_limit,
    )


async def update_card(session: AsyncSession, card_id: int, **fields: object) -> Card:
    card = await cards_crud.get_by_id_for_update(session, card_id)
    if card is None:
        raise NotFoundError("Карта не найдена.")

    if "name" in fields:
        name = str(fields["name"]).strip()
        if not name:
            raise ValidationError("Название карты не может быть пустым.")
        duplicate = await cards_crud.get_by_name(session, name)
        if duplicate is not None and duplicate.id != card.id:
            raise ValidationError(f"Карта «{name}» уже есть в реестре.")
        fields["name"] = name

    if "kind" in fields:
        kind = str(fields["kind"]).strip()
        if not kind:
            raise ValidationError("Вид карты не может быть пустым.")
        fields["kind"] = kind

    if "number" in fields:
        number = fields["number"]
        if card.card_type is not CardType.SPECIAL:
            raise ValidationError("Номер Особого слота допустим только для Особой карты.")
        if number is None:
            raise ValidationError("Особая карта должна иметь номер слота от 0 до 99.")
        if number is not None:
            if not isinstance(number, int) or not 0 <= number <= 99:
                raise ValidationError("Номер Особого слота должен быть от 0 до 99.")
            duplicate = await cards_crud.get_by_number(session, number)
            if duplicate is not None and duplicate.id != card.id:
                raise ValidationError(f"Особый слот №{number} уже занят.")

    new_limit = fields.get("transform_limit", card.transform_limit)
    if card.card_type is not CardType.SPECIAL and new_limit is not None:
        raise ValidationError("Лимит преобразований задаётся только Особым картам.")
    if new_limit is not None:
        if not isinstance(new_limit, int) or new_limit < 1:
            raise ValidationError("Лимит преобразований должен быть целым числом больше нуля.")
        live_copies = await cards_crud.count_owners(session, card.id)
        if new_limit < live_copies:
            raise ValidationError(
                f"Нельзя опустить лимит до {new_limit}: живых копий уже {live_copies}."
            )

    return await cards_crud.update(session, card, **fields)


async def delete_card(session: AsyncSession, card_id: int) -> str:
    card = await cards_crud.get_by_id(session, card_id)
    if card is None:
        raise NotFoundError("Карта не найдена.")
    bound_copies = await cards_crud.count_bound_ownerships(session, card_id)
    if bound_copies:
        raise ValidationError(
            f"Нельзя удалить карту: {bound_copies} её копий связаны с Контурами."
        )
    name = card.name
    await cards_crud.delete(session, card)
    return name


async def find_card(session: AsyncSession, query: str) -> Card:
    """Найти одну карту по точному названию, номеру слота или подстроке."""
    query = query.strip()
    if not query:
        raise ValidationError("Укажите название карты.")

    if query.isdigit():
        number = int(query)
        special = await cards_crud.get_by_number(session, number)
        registry = await cards_crud.get_by_registry_number(session, number)
        if special is not None and registry is not None:
            raise ValidationError(
                f"Номер {number} есть в обоих пулах. Уточните название карты."
            )
        if special is not None or registry is not None:
            return special or registry

    exact = await cards_crud.get_by_name(session, query)
    if exact is not None:
        return exact

    matches = await cards_crud.search_by_name(session, query, limit=6)
    if not matches:
        raise NotFoundError(f"Карта «{query}» в реестре не найдена.")
    if len(matches) > 1:
        names = ", ".join(card.name for card in matches)
        raise ValidationError(f"Под запрос подходит несколько карт: {names}. Уточните название.")
    return matches[0]


def remaining_transforms(card: Card, live_copies: int) -> int | None:
    """Сколько копий ещё можно выдать. None - лимита нет."""
    if card.transform_limit is None:
        return None
    return max(card.transform_limit - live_copies, 0)


async def grant_card(session: AsyncSession, card_id: int, character_id: int) -> CardOwnership:
    """Выдать копию карты персонажу с проверкой лимита преобразований."""
    # Блокировка сериализует параллельные выдачи одной карты в PostgreSQL.
    card = await cards_crud.get_by_id_for_update(session, card_id)
    if card is None:
        raise NotFoundError("Карта не найдена.")
    if card.card_type is CardType.GM:
        raise ValidationError("Карты ГеймМастеров нельзя выдавать персонажам.")

    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")

    live_copies = await cards_crud.count_owners(session, card_id)
    if card.transform_limit is not None and live_copies >= card.transform_limit:
        raise TransformLimitReached(
            f"Лимит преобразований карты «{card.name}» исчерпан: "
            f"{live_copies} из {card.transform_limit} копий уже на руках."
        )

    ownership = await cards_crud.add_ownership(session, card_id, character_id)
    card.copies_count = live_copies + 1
    await session.flush()
    return ownership


async def grant_ordinary_card(
    session: AsyncSession,
    *,
    character_id: int,
    name: str,
    kind: str,
    rarity: Rarity,
    description: str = "",
    usage: str = "",
) -> CardOwnership:
    if not name.strip():
        raise ValidationError("Название Обычной карты не может быть пустым.")
    if not kind.strip():
        raise ValidationError("Вид Обычной карты не может быть пустым.")
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")
    return await cards_crud.add_ordinary_ownership(
        session,
        character_id=character_id,
        name=name,
        kind=kind,
        rarity=rarity,
        description=description,
        usage=usage,
    )


async def revoke_ordinary_card(
    session: AsyncSession, *, character_id: int, name: str
) -> None:
    ownership = await cards_crud.get_free_ordinary_ownership(
        session, character_id, name
    )
    if ownership is None:
        raise NotFoundError(
            "Свободная Обычная карта с таким названием у персонажа не найдена."
        )
    await cards_crud.remove_ownership(session, ownership)


async def revoke_card(session: AsyncSession, card_id: int, character_id: int) -> None:
    """Забрать копию карты - освобождает одно преобразование."""
    ownership = await cards_crud.get_free_ownership(
        session, card_id, character_id
    )
    if ownership is None:
        existing = await cards_crud.get_ownership(session, card_id, character_id)
        if existing is None:
            raise NotFoundError("У этого персонажа такой карты нет.")
        raise ValidationError(
            "Все копии этой карты связаны с Контурами. Сначала измените или "
            "разберите Контур."
        )

    await cards_crud.remove_ownership(session, ownership)

    card = await cards_crud.get_by_id(session, card_id)
    if card is not None:
        card.copies_count = await cards_crud.count_owners(session, card_id)
    await session.flush()


async def recount_copies(session: AsyncSession, card_id: int) -> int:
    """Пересчитать copies_count по таблице владений и починить расхождение."""
    card = await cards_crud.get_by_id(session, card_id)
    if card is None:
        raise NotFoundError("Карта не найдена.")
    card.copies_count = await cards_crud.count_owners(session, card_id)
    await session.flush()
    return card.copies_count
