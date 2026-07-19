from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import CardOwnership, CardType, Character
from bot.services import auth_service
from bot.services.errors import NotFoundError, ValidationError

INITIAL_FREE_SLOTS = 10


@dataclass(frozen=True)
class BookSlotUsage:
    special_used: int
    special_limit: int
    free_used: int
    free_limit: int
    bound_copies: int

    @property
    def free_remaining(self) -> int:
        return self.free_limit - self.free_used


def calculate_usage(
    character: Character,
    ownerships: list[CardOwnership],
    *,
    additionally_bound: set[int] | None = None,
    additionally_free: set[int] | None = None,
) -> BookSlotUsage:
    bind = additionally_bound or set()
    release = additionally_free or set()
    unbound: list[CardOwnership] = []
    bound_count = 0
    for ownership in ownerships:
        is_bound = ownership.contour_component is not None
        if ownership.id in release:
            is_bound = False
        if ownership.id in bind:
            is_bound = True
        if is_bound:
            bound_count += 1
        else:
            unbound.append(ownership)

    special_groups: set[int] = set()
    free_used = 0
    for ownership in unbound:
        if (
            ownership.card is not None
            and ownership.card.card_type is CardType.SPECIAL
            and ownership.card_id not in special_groups
        ):
            special_groups.add(ownership.card_id)
        else:
            free_used += 1
    return BookSlotUsage(
        special_used=len(special_groups),
        special_limit=100,
        free_used=free_used,
        free_limit=character.free_slot_limit,
        bound_copies=bound_count,
    )


async def get_usage(session: AsyncSession, character_id: int) -> BookSlotUsage:
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    ownerships = await cards_crud.list_character_ownerships_for_slots(session, character_id)
    return calculate_usage(character, ownerships)


async def ensure_new_copies_fit(
    session: AsyncSession,
    *,
    character: Character,
    card_types: list[tuple[CardType, int | None]],
) -> None:
    ownerships = await cards_crud.list_character_ownerships_for_slots(session, character.id)
    usage = calculate_usage(character, ownerships)
    occupied_special = {
        item.card_id
        for item in ownerships
        if item.contour_component is None
        and item.card is not None
        and item.card.card_type is CardType.SPECIAL
    }
    extra_free = 0
    for card_type, card_id in card_types:
        if card_type is CardType.SPECIAL and card_id not in occupied_special:
            occupied_special.add(card_id)
        else:
            extra_free += 1
    _ensure_free_capacity(usage, usage.free_used + extra_free)


async def ensure_binding_change_fits(
    session: AsyncSession,
    *,
    character_id: int,
    bind_ids: set[int] | None = None,
    release_ids: set[int] | None = None,
) -> None:
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    ownerships = await cards_crud.list_character_ownerships_for_slots(session, character_id)
    usage = calculate_usage(
        character,
        ownerships,
        additionally_bound=bind_ids,
        additionally_free=release_ids,
    )
    _ensure_free_capacity(usage, usage.free_used)


async def upgrade_free_slot_limit(
    session: AsyncSession, *, character_id: int, admin_vk_id: int
) -> Character:
    auth_service.require_admin(admin_vk_id)
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    character.free_slot_limit += 1
    await session.flush()
    return character


async def set_free_slot_limit(
    session: AsyncSession, *, character_id: int, value: int, admin_vk_id: int
) -> Character:
    auth_service.require_admin(admin_vk_id)
    if value < INITIAL_FREE_SLOTS:
        raise ValidationError("Количество Свободных слотов не может быть меньше 10.")
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    ownerships = await cards_crud.list_character_ownerships_for_slots(session, character_id)
    usage = calculate_usage(character, ownerships)
    if value < usage.free_used:
        raise ValidationError(
            f"Сейчас занято Свободных слотов: {usage.free_used}. "
            "Сначала освободите лишние слоты."
        )
    character.free_slot_limit = value
    await session.flush()
    return character


def _ensure_free_capacity(usage: BookSlotUsage, projected: int) -> None:
    if projected > usage.free_limit:
        needed = projected - usage.free_limit
        raise ValidationError(
            f"Свободные слоты заполнены ({usage.free_used}/{usage.free_limit}). "
            f"Нужно ещё слотов: {needed}."
        )
