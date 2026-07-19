from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import Card, CardOwnership, CardType, CardUsage, Rarity
from bot.services import book_slot_service
from bot.services.errors import NotFoundError, TransformLimitReached, ValidationError

MAX_CARD_QUANTITY = 999


@dataclass(frozen=True)
class CardConsumption:
    usage_id: int
    character_id: int
    character_name: str
    card_name: str
    card_type: CardType
    quantity: int
    remaining_free: int


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
    if card_type in (CardType.SPELL, CardType.CONTOUR, CardType.GM):
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
        card = (
            await cards_crud.get_by_number(session, number)
            if number < 100
            else await cards_crud.get_by_registry_number(session, number)
        )
        if card is not None:
            return card

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
    return (await grant_card_copies(session, card_id, character_id, quantity=1))[0]


async def grant_card_copies(
    session: AsyncSession,
    card_id: int,
    character_id: int,
    *,
    quantity: int,
) -> list[CardOwnership]:
    """Atomically grant several independent physical copies."""
    quantity = _validate_quantity(quantity)
    # Блокировка сериализует параллельные выдачи одной карты в PostgreSQL.
    card = await cards_crud.get_by_id_for_update(session, card_id)
    if card is None:
        raise NotFoundError("Карта не найдена.")
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")

    live_copies = await cards_crud.count_owners(session, card_id)
    if (
        card.transform_limit is not None
        and live_copies + quantity > card.transform_limit
    ):
        raise TransformLimitReached(
            f"Нельзя выдать {quantity} коп.: у карты «{card.name}» уже "
            f"{live_copies} из {card.transform_limit} допустимых копий."
        )

    await book_slot_service.ensure_new_copies_fit(
        session,
        character=character,
        card_types=[(card.card_type, card.id)] * quantity,
    )

    ownerships = [
        CardOwnership(card_id=card_id, character_id=character_id)
        for _ in range(quantity)
    ]
    session.add_all(ownerships)
    card.copies_count = live_copies + quantity
    await session.flush()
    return ownerships


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
    return (
        await grant_ordinary_cards(
            session,
            character_id=character_id,
            name=name,
            kind=kind,
            rarity=rarity,
            description=description,
            usage=usage,
            quantity=1,
        )
    )[0]


async def grant_ordinary_cards(
    session: AsyncSession,
    *,
    character_id: int,
    name: str,
    kind: str,
    rarity: Rarity,
    description: str = "",
    usage: str = "",
    quantity: int,
) -> list[CardOwnership]:
    quantity = _validate_quantity(quantity)
    if not name.strip():
        raise ValidationError("Название Обычной карты не может быть пустым.")
    if not kind.strip():
        raise ValidationError("Вид Обычной карты не может быть пустым.")
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")
    await book_slot_service.ensure_new_copies_fit(
        session,
        character=character,
        card_types=[(CardType.ORDINARY, None)] * quantity,
    )
    ownerships = [
        CardOwnership(
            character_id=character_id,
            card_id=None,
            ordinary_name=name.strip(),
            ordinary_kind=kind.strip(),
            ordinary_rarity=rarity,
            ordinary_description=description.strip(),
            ordinary_usage=usage.strip(),
        )
        for _ in range(quantity)
    ]
    session.add_all(ownerships)
    await session.flush()
    return ownerships


async def revoke_ordinary_card(
    session: AsyncSession, *, character_id: int, name: str
) -> None:
    await revoke_ordinary_cards(
        session, character_id=character_id, name=name, quantity=1
    )


async def revoke_ordinary_cards(
    session: AsyncSession, *, character_id: int, name: str, quantity: int
) -> list[int]:
    quantity = _validate_quantity(quantity)
    ownerships = await cards_crud.list_free_ordinary_ownerships(
        session, character_id, name
    )
    if not ownerships:
        raise NotFoundError(
            "Свободная Обычная карта с таким названием у персонажа не найдена."
        )
    if len(ownerships) < quantity:
        raise ValidationError(
            f"Свободных копий карты «{name.strip()}» только {len(ownerships)}, "
            f"а запрошено {quantity}."
        )
    selected = ownerships[:quantity]
    ids = [item.id for item in selected]
    for ownership in selected:
        await session.delete(ownership)
    await session.flush()
    return ids


async def revoke_card(session: AsyncSession, card_id: int, character_id: int) -> None:
    """Забрать копию карты - освобождает одно преобразование."""
    await revoke_card_copies(session, card_id, character_id, quantity=1)


async def revoke_card_copies(
    session: AsyncSession,
    card_id: int,
    character_id: int,
    *,
    quantity: int,
) -> list[int]:
    quantity = _validate_quantity(quantity)
    card = await cards_crud.get_by_id_for_update(session, card_id)
    if card is None:
        raise NotFoundError("Карта не найдена.")
    ownerships = await cards_crud.list_free_ownerships(
        session, card_id, character_id
    )
    if not ownerships:
        existing = await cards_crud.get_ownership(session, card_id, character_id)
        if existing is None:
            raise NotFoundError("У этого персонажа такой карты нет.")
        raise ValidationError(
            "Все копии этой карты связаны с Контурами. Сначала измените или "
            "разберите Контур."
        )
    if len(ownerships) < quantity:
        raise ValidationError(
            f"Свободных копий карты «{card.name}» только {len(ownerships)}, "
            f"а запрошено {quantity}. Связанные копии не списываются."
        )
    selected = ownerships[:quantity]
    ids = [item.id for item in selected]
    live_copies = await cards_crud.count_owners(session, card_id)
    for ownership in selected:
        await session.delete(ownership)
    card.copies_count = max(live_copies - quantity, 0)
    await session.flush()
    return ids


async def consume_card(
    session: AsyncSession,
    *,
    character_id: int,
    used_by_vk_id: int,
    name: str,
    quantity: int,
    target_vk_id: int | None,
    peer_id: int,
    conversation_message_id: int | None,
) -> CardConsumption:
    """Consume free Spell or Ordinary copies and write an immutable audit row."""
    quantity = _validate_quantity(quantity)
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")
    if character.vk_id != used_by_vk_id:
        raise ValidationError("Можно расходовать карты только собственной анкеты.")

    ownerships = await cards_crud.list_free_consumable_ownerships(
        session, character_id, name
    )
    if not ownerships:
        all_items = await cards_crud.list_character_ownerships(session, character_id)
        bound = [
            item
            for item in all_items
            if item.display_name.casefold() == name.strip().casefold()
            and item.display_type in {CardType.SPELL, CardType.ORDINARY}
            and item.contour_component is not None
        ]
        if bound:
            raise ValidationError(
                "Все подходящие копии связаны с Контурами и не могут быть потрачены."
            )
        raise NotFoundError(
            "Свободная Карта Заклинаний или Обычная карта с таким названием не найдена."
        )

    groups = {
        (item.display_type, item.card_id if item.card_id is not None else "ordinary")
        for item in ownerships
    }
    if len(groups) > 1:
        raise ValidationError(
            "Найдены и реестровая, и Обычная карта с таким названием. "
            "Переименуйте Обычную карту или расходуйте её через администратора."
        )
    if len(ownerships) < quantity:
        raise ValidationError(
            f"Свободных копий «{ownerships[0].display_name}» только "
            f"{len(ownerships)}, а запрошено {quantity}."
        )

    selected = ownerships[:quantity]
    first = selected[0]
    ownership_ids = [item.id for item in selected]
    usage = CardUsage(
        character_id=character.id,
        card_id=first.card_id,
        character_name=character.name,
        card_name=first.display_name,
        card_type=first.display_type,
        quantity=quantity,
        ownership_ids=ownership_ids,
        used_by_vk_id=used_by_vk_id,
        target_vk_id=target_vk_id,
        peer_id=peer_id,
        conversation_message_id=conversation_message_id,
    )
    session.add(usage)
    for ownership in selected:
        await session.delete(ownership)
    if first.card is not None:
        live_copies = await cards_crud.count_owners(session, first.card.id)
        first.card.copies_count = max(live_copies - quantity, 0)
    await session.flush()
    return CardConsumption(
        usage_id=usage.id,
        character_id=character.id,
        character_name=character.name,
        card_name=first.display_name,
        card_type=first.display_type,
        quantity=quantity,
        remaining_free=len(ownerships) - quantity,
    )


async def recount_copies(session: AsyncSession, card_id: int) -> int:
    """Пересчитать copies_count по таблице владений и починить расхождение."""
    card = await cards_crud.get_by_id(session, card_id)
    if card is None:
        raise NotFoundError("Карта не найдена.")
    card.copies_count = await cards_crud.count_owners(session, card_id)
    await session.flush()
    return card.copies_count


def _validate_quantity(quantity: int) -> int:
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValidationError("Количество карт должно быть целым числом.")
    if not 1 <= quantity <= MAX_CARD_QUANTITY:
        raise ValidationError(
            f"Количество карт должно быть от 1 до {MAX_CARD_QUANTITY}."
        )
    return quantity
