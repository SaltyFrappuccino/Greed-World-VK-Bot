from unittest.mock import AsyncMock

import pytest

from bot.database.models import CardType
from bot.handlers.dm.admin import cards
from bot.services.card_template_service import CONTOUR_SUBTYPES
from bot.states import AdminCardState, clear_state, state_dispenser


class _Message:
    from_id = 99

    def __init__(self, peer_id: int, payload: dict[str, object]):
        self.peer_id = peer_id
        self._payload = payload
        self.answers: list[tuple[str, dict[str, object]]] = []

    def get_payload_json(self):
        return self._payload

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


@pytest.mark.asyncio
async def test_card_type_offers_wizard_or_full_template():
    message = _Message(5101, {"cmd": "admin_card_add_wizard"})
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.ADD_MODE,
        card_type=CardType.ORDINARY.name,
    )

    await cards.choose_wizard_mode(message)

    state = await state_dispenser.get(message.peer_id)
    assert state is not None
    assert state.state == AdminCardState.ADD_NAME
    await clear_state(message.peer_id)

    message = _Message(5102, {"cmd": "admin_card_add_template"})
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.ADD_MODE,
        card_type=CardType.ORDINARY.name,
    )

    await cards.choose_template_mode(message)

    state = await state_dispenser.get(message.peer_id)
    assert state is not None
    assert state.state == AdminCardState.ADD_TEMPLATE
    assert "Название:" in message.answers[-1][0]
    await clear_state(message.peer_id)


@pytest.mark.asyncio
async def test_contour_subtype_and_rarity_are_button_steps():
    message = _Message(
        5103,
        {
            "cmd": "admin_card_contour_subtype",
            "subtype": "Эффект — Связь",
        },
    )
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.ADD_CONTOUR_SUBTYPE,
        card_type=CardType.CONTOUR.name,
        name="Связующая нить",
    )

    await cards.choose_contour_subtype(message)

    state = await state_dispenser.get(message.peer_id)
    assert state is not None
    assert state.state == AdminCardState.ADD_RARITY
    assert state.payload["kind"] == "Эффект — Связь"

    message._payload = {"cmd": "admin_card_rarity", "rarity": "B"}
    await cards.choose_rarity(message)

    state = await state_dispenser.get(message.peer_id)
    assert state is not None
    assert state.state == AdminCardState.ADD_DESCRIPTION
    assert state.payload["rarity"] == "B"
    await clear_state(message.peer_id)


@pytest.mark.asyncio
async def test_special_rarity_leads_to_slot_and_limit_steps():
    message = _Message(5104, {"cmd": "admin_card_rarity", "rarity": "S"})
    await state_dispenser.set(
        message.peer_id,
        AdminCardState.ADD_RARITY,
        card_type=CardType.SPECIAL.name,
        name="Ясень",
        kind=CardType.SPECIAL.value,
    )

    await cards.choose_rarity(message)

    state = await state_dispenser.get(message.peer_id)
    assert state is not None
    assert state.state == AdminCardState.ADD_NUMBER
    assert state.payload["rarity"] == "S"
    await clear_state(message.peer_id)


@pytest.mark.asyncio
async def test_spell_fields_are_combined_without_losing_labels(monkeypatch):
    message = _Message(5105, {})
    payload = {
        "card_type": CardType.SPELL.name,
        "name": "Тихий зов",
        "kind": CardType.SPELL.value,
        "rarity": "A",
    }

    await cards._after_description(message, payload, "Призывает существо")
    state = await state_dispenser.get(message.peer_id)
    assert state is not None
    assert state.state == AdminCardState.ADD_SPELL_ACTIVATION

    await cards._after_spell_activation(
        message, dict(state.payload), "Назвать цель"
    )
    state = await state_dispenser.get(message.peer_id)
    assert state is not None
    assert state.state == AdminCardState.ADD_SPELL_CONSUMPTION

    create_mock = AsyncMock()
    monkeypatch.setattr(cards, "_create_wizard_card", create_mock)
    final_payload = dict(state.payload)
    final_payload["consumption"] = "Исчезает после применения"
    await cards._create_spell_card(message, final_payload)

    saved_payload = create_mock.await_args.args[1]
    assert saved_payload["usage"] == (
        "Команда активации: Назвать цель\n"
        "Расходование: Исчезает после применения"
    )
    await clear_state(message.peer_id)


def test_all_system_contour_subtypes_are_available():
    assert CONTOUR_SUBTYPES == (
        "Форма — Покров",
        "Форма — Оружие",
        "Форма — Снаряд",
        "Форма — Область",
        "Форма — Ловушка",
        "Форма — Барьер",
        "Эффект — Существо",
        "Эффект — Метка",
        "Эффект — Превращение",
        "Эффект — Связь",
    )
