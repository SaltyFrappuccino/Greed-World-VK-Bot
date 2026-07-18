from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import contours as contours_crud
from bot.database.models import CardOwnership, CardType, Character, Contour
from bot.services import auth_service
from bot.services.errors import NotFoundError, PermissionDenied, ValidationError

MIN_CONTOUR_LIMIT = 2
MIN_CARD_CAPACITY = 2
MAX_CARD_CAPACITY = 5

EDITABLE_FIELDS = {
    "name",
    "appearance",
    "primary_effect",
    "additional_capabilities",
    "activation_conditions",
    "duration",
    "conductivity",
    "overload_impact",
}


async def create_contour(
    session: AsyncSession,
    *,
    character_id: int,
    ownership_ids: list[int],
    name: str,
    admin_vk_id: int,
    slot: int | None = None,
    card_capacity: int = MIN_CARD_CAPACITY,
    **fields: object,
) -> Contour:
    auth_service.require_admin(admin_vk_id)
    if not name.strip():
        raise ValidationError("Название Контура не может быть пустым.")
    _validate_capacity(card_capacity)

    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")

    contours = await contours_crud.list_for_character(session, character_id)
    occupied = {contour.slot for contour in contours}
    if slot is None:
        slot = next(
            (
                candidate
                for candidate in range(1, character.contour_limit + 1)
                if candidate not in occupied
            ),
            None,
        )
    if slot is None:
        raise ValidationError(
            f"У персонажа {character.name} заняты все {character.contour_limit} "
            "слотов Контуров."
        )
    if not 1 <= slot <= character.contour_limit:
        raise ValidationError(
            f"Слот должен быть от 1 до {character.contour_limit}."
        )
    if slot in occupied:
        raise ValidationError(f"Слот {slot} уже занят другим Контуром.")

    ownerships = await _validated_ownerships(
        session,
        character_id=character_id,
        ownership_ids=ownership_ids,
        capacity=card_capacity,
    )
    contour = await contours_crud.create(
        session,
        character_id=character_id,
        slot=slot,
        name=name,
        created_by=admin_vk_id,
        card_capacity=card_capacity,
        composition=_composition(ownerships),
        **{key: value for key, value in fields.items() if key in EDITABLE_FIELDS - {"name"}},
    )
    for position, ownership in enumerate(ownerships, start=1):
        await contours_crud.add_component(
            session,
            contour_id=contour.id,
            ownership_id=ownership.id,
            position=position,
        )
    return await _require_contour(session, contour.id)


async def list_for_character(
    session: AsyncSession, character_id: int
) -> list[Contour]:
    return await contours_crud.list_for_character(session, character_id)


async def require_visible_character(
    session: AsyncSession,
    *,
    character_id: int,
    viewer_vk_id: int,
) -> Character:
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    if character.vk_id != viewer_vk_id and not _is_admin(viewer_vk_id):
        raise PermissionDenied("Контуры доступны только владельцу анкеты и администратору.")
    return character


async def require_visible_contour(
    session: AsyncSession,
    *,
    contour_id: int,
    viewer_vk_id: int,
) -> Contour:
    contour = await _require_contour(session, contour_id)
    await require_visible_character(
        session,
        character_id=contour.character_id,
        viewer_vk_id=viewer_vk_id,
    )
    return contour


async def upgrade_character_limit(
    session: AsyncSession, *, character_id: int, admin_vk_id: int
) -> Character:
    auth_service.require_admin(admin_vk_id)
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    return await characters_crud.update(
        session, character, contour_limit=character.contour_limit + 1
    )


async def set_character_limit(
    session: AsyncSession,
    *,
    character_id: int,
    value: int,
    admin_vk_id: int,
) -> Character:
    auth_service.require_admin(admin_vk_id)
    if value < MIN_CONTOUR_LIMIT:
        raise ValidationError(
            f"Лимит Контуров не может быть меньше {MIN_CONTOUR_LIMIT}."
        )
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    contours = await contours_crud.list_for_character(session, character_id)
    highest_slot = max((contour.slot for contour in contours), default=0)
    if value < highest_slot:
        raise ValidationError(
            f"Слот {highest_slot} уже занят. Сначала разберите Контуры за новым лимитом."
        )
    return await characters_crud.update(session, character, contour_limit=value)


async def upgrade_capacity(
    session: AsyncSession, *, contour_id: int, admin_vk_id: int
) -> Contour:
    auth_service.require_admin(admin_vk_id)
    contour = await _require_contour_for_update(session, contour_id)
    if contour.card_capacity >= MAX_CARD_CAPACITY:
        raise ValidationError("Размер Контура уже максимальный — 5 карт.")
    return await contours_crud.update(
        session, contour, card_capacity=contour.card_capacity + 1
    )


async def set_capacity(
    session: AsyncSession,
    *,
    contour_id: int,
    value: int,
    admin_vk_id: int,
) -> Contour:
    auth_service.require_admin(admin_vk_id)
    _validate_capacity(value)
    contour = await _require_contour_for_update(session, contour_id)
    if value < len(contour.components):
        raise ValidationError(
            f"В Контуре уже {len(contour.components)} карт. Сначала уменьшите состав."
        )
    return await contours_crud.update(session, contour, card_capacity=value)


async def update_contour(
    session: AsyncSession,
    *,
    contour_id: int,
    admin_vk_id: int,
    **fields: object,
) -> Contour:
    auth_service.require_admin(admin_vk_id)
    unknown = set(fields) - EDITABLE_FIELDS
    if unknown:
        raise ValidationError(
            "Нельзя редактировать поля: " + ", ".join(sorted(unknown))
        )
    if "name" in fields:
        name = str(fields["name"]).strip()
        if not name:
            raise ValidationError("Название Контура не может быть пустым.")
        fields["name"] = name
    contour = await _require_contour_for_update(session, contour_id)
    return await contours_crud.update(session, contour, **fields)


async def add_card(
    session: AsyncSession,
    *,
    contour_id: int,
    ownership_id: int,
    admin_vk_id: int,
) -> Contour:
    auth_service.require_admin(admin_vk_id)
    contour = await _require_contour_for_update(session, contour_id)
    ids = [component.card_ownership_id for component in contour.components]
    ids.append(ownership_id)
    ownerships = await _validated_ownerships(
        session,
        character_id=contour.character_id,
        ownership_ids=ids,
        capacity=contour.card_capacity,
        allowed_contour_id=contour.id,
    )
    await contours_crud.add_component(
        session,
        contour_id=contour.id,
        ownership_id=ownership_id,
        position=len(contour.components) + 1,
    )
    contour.composition = _composition(ownerships)
    await session.flush()
    return await _require_contour(session, contour.id)


async def set_cards(
    session: AsyncSession,
    *,
    contour_id: int,
    ownership_ids: list[int],
    admin_vk_id: int,
) -> Contour:
    """Полностью перепривязать состав, в том числе у legacy-Контура."""
    auth_service.require_admin(admin_vk_id)
    contour = await _require_contour_for_update(session, contour_id)
    ownerships = await _validated_ownerships(
        session,
        character_id=contour.character_id,
        ownership_ids=ownership_ids,
        capacity=contour.card_capacity,
        allowed_contour_id=contour.id,
    )
    for component in list(contour.components):
        await contours_crud.delete_component(session, component)
    for position, ownership in enumerate(ownerships, start=1):
        await contours_crud.add_component(
            session,
            contour_id=contour.id,
            ownership_id=ownership.id,
            position=position,
        )
    contour.composition = _composition(ownerships)
    await session.flush()
    return await _require_contour(session, contour.id)


async def remove_card(
    session: AsyncSession,
    *,
    component_id: int,
    admin_vk_id: int,
) -> Contour:
    auth_service.require_admin(admin_vk_id)
    component = await contours_crud.get_component(session, component_id)
    if component is None:
        raise NotFoundError("Компонент Контура не найден.")
    contour = await _require_contour_for_update(session, component.contour_id)
    remaining_ids = [
        item.card_ownership_id
        for item in contour.components
        if item.id != component_id
    ]
    ownerships = await _validated_ownerships(
        session,
        character_id=contour.character_id,
        ownership_ids=remaining_ids,
        capacity=contour.card_capacity,
        allowed_contour_id=contour.id,
    )
    await contours_crud.delete_component(session, component)
    remaining = [item for item in contour.components if item.id != component_id]
    for position, item in enumerate(remaining, start=1):
        item.position = position
    contour.composition = _composition(ownerships)
    await session.flush()
    return await _require_contour(session, contour.id)


async def replace_card(
    session: AsyncSession,
    *,
    component_id: int,
    ownership_id: int,
    admin_vk_id: int,
) -> Contour:
    auth_service.require_admin(admin_vk_id)
    component = await contours_crud.get_component(session, component_id)
    if component is None:
        raise NotFoundError("Компонент Контура не найден.")
    contour = await _require_contour_for_update(session, component.contour_id)
    ids = [
        ownership_id if item.id == component_id else item.card_ownership_id
        for item in contour.components
    ]
    ownerships = await _validated_ownerships(
        session,
        character_id=contour.character_id,
        ownership_ids=ids,
        capacity=contour.card_capacity,
        allowed_contour_id=contour.id,
    )
    component.card_ownership_id = ownership_id
    contour.composition = _composition(ownerships)
    await session.flush()
    return await _require_contour(session, contour.id)


async def disassemble(
    session: AsyncSession, *, contour_id: int, admin_vk_id: int
) -> tuple[int, str]:
    auth_service.require_admin(admin_vk_id)
    contour = await _require_contour_for_update(session, contour_id)
    character_id, name = contour.character_id, contour.name
    await contours_crud.delete(session, contour)
    return character_id, name


async def _validated_ownerships(
    session: AsyncSession,
    *,
    character_id: int,
    ownership_ids: list[int],
    capacity: int,
    allowed_contour_id: int | None = None,
) -> list[CardOwnership]:
    if len(ownership_ids) < MIN_CARD_CAPACITY:
        raise ValidationError("В Контуре должно быть минимум 2 карты.")
    if len(ownership_ids) > capacity:
        raise ValidationError(f"Размер этого Контура — не больше {capacity} карт.")
    if len(set(ownership_ids)) != len(ownership_ids):
        raise ValidationError("Одна копия карты выбрана несколько раз.")

    ownerships: list[CardOwnership] = []
    for ownership_id in ownership_ids:
        ownership = await cards_crud.get_ownership_by_id(session, ownership_id)
        if ownership is None or ownership.character_id != character_id:
            raise ValidationError("Выбранная копия карты не принадлежит персонажу.")
        bound = ownership.contour_component
        if bound is not None and bound.contour_id != allowed_contour_id:
            raise ValidationError(
                f"Копия карты «{ownership.card.name}» уже связана с другим Контуром."
            )
        ownerships.append(ownership)

    card_ids = [ownership.card_id for ownership in ownerships]
    if len(set(card_ids)) != len(card_ids):
        raise ValidationError("В один Контур нельзя вставить две одинаковые карты.")
    if not any(ownership.card.card_type is CardType.CONTOUR for ownership in ownerships):
        raise ValidationError("В составе должна быть хотя бы одна Контурная карта.")
    return ownerships


def _composition(ownerships: list[CardOwnership]) -> str:
    return " + ".join(ownership.card.name for ownership in ownerships)


def _validate_capacity(value: int) -> None:
    if not MIN_CARD_CAPACITY <= value <= MAX_CARD_CAPACITY:
        raise ValidationError("Размер Контура должен быть от 2 до 5 карт.")


async def _require_contour(session: AsyncSession, contour_id: int) -> Contour:
    contour = await contours_crud.get_by_id(session, contour_id)
    if contour is None:
        raise NotFoundError("Контур не найден.")
    return contour


async def _require_contour_for_update(
    session: AsyncSession, contour_id: int
) -> Contour:
    contour = await contours_crud.get_by_id_for_update(session, contour_id)
    if contour is None:
        raise NotFoundError("Контур не найден.")
    return contour


def _is_admin(vk_id: int) -> bool:
    try:
        auth_service.require_admin(vk_id)
    except PermissionDenied:
        return False
    return True
