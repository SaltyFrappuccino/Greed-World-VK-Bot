import pytest

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import CardType, Rarity
from bot.services import auth_service, card_service, contour_service
from bot.services.errors import PermissionDenied, ValidationError


@pytest.fixture(autouse=True)
def allow_test_admin(monkeypatch):
    monkeypatch.setattr(auth_service, "require_admin", lambda _vk_id: None)


async def _card_copy(session, character_id, name, card_type=CardType.SPELL):
    if card_type is CardType.ORDINARY:
        ownership = await card_service.grant_ordinary_card(
            session,
            character_id=character_id,
            name=name,
            kind="Предмет",
            rarity=Rarity.H,
        )
        return None, ownership
    card = await card_service.create_card(
        session,
        name=name,
        card_type=card_type,
        kind=card_type.value,
        rarity=Rarity.H,
        admin_vk_id=99,
    )
    ownership = await card_service.grant_card(session, card.id, character_id)
    return card, ownership


@pytest.mark.asyncio
async def test_character_starts_with_two_contours_of_size_two(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    _, form = await _card_copy(session, character.id, "Покров", CardType.CONTOUR)
    _, lightning = await _card_copy(session, character.id, "Молния")
    _, weapon = await _card_copy(session, character.id, "Оружие", CardType.CONTOUR)
    _, fire = await _card_copy(session, character.id, "Огонь")

    first = await contour_service.create_contour(
        session,
        character_id=character.id,
        ownership_ids=[form.id, lightning.id],
        name="Первый",
        admin_vk_id=99,
    )
    second = await contour_service.create_contour(
        session,
        character_id=character.id,
        ownership_ids=[weapon.id, fire.id],
        name="Второй",
        admin_vk_id=99,
    )

    assert character.contour_limit == 2
    assert (first.slot, second.slot) == (1, 2)
    assert first.card_capacity == 2
    with pytest.raises(ValidationError, match="заняты все 2"):
        await contour_service.create_contour(
            session,
            character_id=character.id,
            ownership_ids=[form.id, fire.id],
            name="Третий",
            admin_vk_id=99,
        )


@pytest.mark.asyncio
async def test_contour_count_and_each_capacity_upgrade_independently(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    _, form = await _card_copy(session, character.id, "Покров", CardType.CONTOUR)
    _, lightning = await _card_copy(session, character.id, "Молния")
    _, speed = await _card_copy(session, character.id, "Скорость")
    contour = await contour_service.create_contour(
        session,
        character_id=character.id,
        ownership_ids=[form.id, lightning.id],
        name="Гроза",
        admin_vk_id=99,
    )

    await contour_service.upgrade_character_limit(
        session, character_id=character.id, admin_vk_id=99
    )
    contour = await contour_service.upgrade_capacity(
        session, contour_id=contour.id, admin_vk_id=99
    )
    contour = await contour_service.add_card(
        session,
        contour_id=contour.id,
        ownership_id=speed.id,
        admin_vk_id=99,
    )

    assert character.contour_limit == 3
    assert contour.card_capacity == 3
    assert [item.ownership.display_name for item in contour.components] == [
        "Покров",
        "Молния",
        "Скорость",
    ]


@pytest.mark.asyncio
async def test_capacity_is_limited_to_five_and_cannot_drop_below_card_count(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    ownerships = []
    for index, card_type in enumerate(
        [CardType.CONTOUR, CardType.ORDINARY, CardType.SPELL]
    ):
        _, ownership = await _card_copy(
            session, character.id, f"Карта {index}", card_type
        )
        ownerships.append(ownership)
    contour = await contour_service.create_contour(
        session,
        character_id=character.id,
        ownership_ids=[item.id for item in ownerships],
        name="Большой",
        card_capacity=3,
        admin_vk_id=99,
    )
    await contour_service.set_capacity(
        session, contour_id=contour.id, value=5, admin_vk_id=99
    )

    with pytest.raises(ValidationError, match="от 2 до 5"):
        await contour_service.set_capacity(
            session, contour_id=contour.id, value=6, admin_vk_id=99
        )
    with pytest.raises(ValidationError, match="уже 3 карт"):
        await contour_service.set_capacity(
            session, contour_id=contour.id, value=2, admin_vk_id=99
        )


@pytest.mark.asyncio
async def test_composition_rules_are_enforced(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    _, ordinary = await _card_copy(session, character.id, "Пепел")
    _, another = await _card_copy(session, character.id, "Огонь")
    contour_card, form = await _card_copy(
        session, character.id, "Покров", CardType.CONTOUR
    )
    duplicate = await card_service.grant_card(session, contour_card.id, character.id)

    with pytest.raises(ValidationError, match="минимум 2"):
        await contour_service.create_contour(
            session,
            character_id=character.id,
            ownership_ids=[form.id],
            name="Один",
            admin_vk_id=99,
        )
    with pytest.raises(ValidationError, match="Контурная"):
        await contour_service.create_contour(
            session,
            character_id=character.id,
            ownership_ids=[ordinary.id, another.id],
            name="Без формы",
            admin_vk_id=99,
        )
    with pytest.raises(ValidationError, match="две одинаковые"):
        await contour_service.create_contour(
            session,
            character_id=character.id,
            ownership_ids=[form.id, duplicate.id],
            name="Дубликат",
            admin_vk_id=99,
        )


@pytest.mark.asyncio
async def test_bound_copy_cannot_be_reused_or_revoked_and_is_freed_on_disassembly(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    _, form = await _card_copy(session, character.id, "Покров", CardType.CONTOUR)
    card, lightning = await _card_copy(session, character.id, "Молния")
    _, weapon = await _card_copy(session, character.id, "Оружие", CardType.CONTOUR)
    contour = await contour_service.create_contour(
        session,
        character_id=character.id,
        ownership_ids=[form.id, lightning.id],
        name="Гроза",
        admin_vk_id=99,
    )
    await contour_service.upgrade_character_limit(
        session, character_id=character.id, admin_vk_id=99
    )

    with pytest.raises(ValidationError, match="другим Контуром"):
        await contour_service.create_contour(
            session,
            character_id=character.id,
            ownership_ids=[weapon.id, lightning.id],
            name="Повтор",
            admin_vk_id=99,
        )
    with pytest.raises(ValidationError, match="Все копии"):
        await card_service.revoke_card(session, card.id, character.id)

    await contour_service.disassemble(
        session, contour_id=contour.id, admin_vk_id=99
    )
    assert await cards_crud.get_free_ownership(session, card.id, character.id)


@pytest.mark.asyncio
async def test_registry_card_cannot_be_deleted_while_bound(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    _, form = await _card_copy(session, character.id, "Покров", CardType.CONTOUR)
    card, lightning = await _card_copy(session, character.id, "Молния")
    await contour_service.create_contour(
        session,
        character_id=character.id,
        ownership_ids=[form.id, lightning.id],
        name="Гроза",
        admin_vk_id=99,
    )

    with pytest.raises(ValidationError, match="связаны с Контурами"):
        await card_service.delete_card(session, card.id)


@pytest.mark.asyncio
async def test_cards_can_be_replaced_and_removed_without_breaking_contour_rules(session):
    character = await characters_crud.create(session, vk_id=1, name="Ава")
    _, form = await _card_copy(session, character.id, "Покров", CardType.CONTOUR)
    _, lightning = await _card_copy(session, character.id, "Молния")
    _, speed = await _card_copy(session, character.id, "Скорость")
    _, fire = await _card_copy(session, character.id, "Огонь")
    contour = await contour_service.create_contour(
        session,
        character_id=character.id,
        ownership_ids=[form.id, lightning.id, speed.id],
        name="Гроза",
        card_capacity=3,
        admin_vk_id=99,
    )

    lightning_component = next(
        item for item in contour.components if item.ownership.display_name == "Молния"
    )
    contour = await contour_service.replace_card(
        session,
        component_id=lightning_component.id,
        ownership_id=fire.id,
        admin_vk_id=99,
    )
    speed_component = next(
        item for item in contour.components if item.ownership.display_name == "Скорость"
    )
    contour = await contour_service.remove_card(
        session, component_id=speed_component.id, admin_vk_id=99
    )

    assert [item.ownership.display_name for item in contour.components] == [
        "Покров",
        "Огонь",
    ]
    form_component = next(
        item for item in contour.components if item.ownership.display_name == "Покров"
    )
    with pytest.raises(ValidationError, match="минимум 2"):
        await contour_service.remove_card(
            session, component_id=form_component.id, admin_vk_id=99
        )


@pytest.mark.asyncio
async def test_owner_can_read_but_cannot_mutate_without_admin_role(session, monkeypatch):
    character = await characters_crud.create(session, vk_id=123, name="Ава")
    def deny(_vk_id):
        raise PermissionDenied("Только администратор")

    monkeypatch.setattr(auth_service, "require_admin", deny)
    await contour_service.require_visible_character(
        session, character_id=character.id, viewer_vk_id=123
    )
    with pytest.raises(PermissionDenied):
        await contour_service.require_visible_character(
            session, character_id=character.id, viewer_vk_id=456
        )
    with pytest.raises(PermissionDenied):
        await contour_service.upgrade_character_limit(
            session, character_id=character.id, admin_vk_id=123
        )
