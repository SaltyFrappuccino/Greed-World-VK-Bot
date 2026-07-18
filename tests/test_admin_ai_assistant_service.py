import pytest

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.services import ai_service
from bot.services import admin_ai_assistant_service as service
from bot.services.errors import ValidationError
from bot.services.errors import PermissionDenied


@pytest.fixture(autouse=True)
def allow_admin(monkeypatch):
    monkeypatch.setattr(service.auth_service, "require_admin", lambda _vk_id: None)


async def _session_and_character(session):
    character = await characters_crud.create(
        session, vk_id=100, name="Ава", is_approved=True
    )
    ai_session = await service.open_session(
        session, admin_vk_id=500, peer_id=500
    )
    return ai_session, character


@pytest.mark.asyncio
async def test_write_plan_changes_nothing_until_confirm_and_is_idempotent(session):
    ai_session, character = await _session_and_character(session)
    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Начислить Шакеи",
        actions=[
            {
                "name": "shakei_change",
                "arguments": {"character_id": character.id, "delta": 100},
                "description": "Начислить Аве 100 Шакеев",
            }
        ],
        warnings=[],
    )

    assert character.shakei_balance == 0
    executed, done = await service.confirm_plan(
        session,
        plan_id=plan.id,
        admin_vk_id=500,
        peer_id=500,
    )
    assert done is True
    assert executed.status == "executed"
    assert character.shakei_balance == 100

    with pytest.raises(ValidationError, match="уже выполнен"):
        await service.confirm_plan(
            session,
            plan_id=plan.id,
            admin_vk_id=500,
            peer_id=500,
        )
    assert character.shakei_balance == 100


@pytest.mark.asyncio
async def test_destructive_plan_requires_second_confirmation(session):
    ai_session, character = await _session_and_character(session)
    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Удалить анкету",
        actions=[
            {
                "name": "character_delete",
                "arguments": {"character_id": character.id},
                "description": "Удалить анкету Авы",
            }
        ],
        warnings=[],
    )

    waiting, done = await service.confirm_plan(
        session, plan_id=plan.id, admin_vk_id=500, peer_id=500
    )
    assert done is False
    assert waiting.status == "awaiting_destructive_confirmation"
    assert await characters_crud.get_by_id(session, character.id) is not None

    executed, done = await service.confirm_plan(
        session,
        plan_id=plan.id,
        admin_vk_id=500,
        peer_id=500,
        destructive_confirmed=True,
    )
    assert done is True
    assert executed.status == "executed"
    assert await characters_crud.get_by_id(session, character.id) is None


@pytest.mark.asyncio
async def test_plan_rejects_unknown_tool_arguments_and_model_admin_id(session):
    ai_session, character = await _session_and_character(session)
    with pytest.raises(ValidationError, match="запрещённые аргументы"):
        await service.create_plan(
            session,
            ai_session=ai_session,
            admin_vk_id=500,
            summary="Подмена прав",
            actions=[
                {
                    "name": "shakei_change",
                    "arguments": {
                        "character_id": character.id,
                        "delta": 100,
                        "admin_vk_id": 1,
                    },
                    "description": "Попытка",
                }
            ],
            warnings=[],
        )


@pytest.mark.asyncio
async def test_stale_plan_is_not_executed(session):
    ai_session, character = await _session_and_character(session)
    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Изменить рейтинг",
        actions=[
            {
                "name": "character_set_rating",
                "arguments": {"character_id": character.id, "rating": "G"},
                "description": "Поставить рейтинг G",
            }
        ],
        warnings=[],
    )
    character.personality = "Изменено параллельно"
    await session.flush()

    with pytest.raises(ValidationError, match="Данные изменились"):
        await service.confirm_plan(
            session, plan_id=plan.id, admin_vk_id=500, peer_id=500
        )
    assert character.overall_rating.value == "H"


@pytest.mark.asyncio
async def test_action_batch_rolls_back_when_later_action_fails(session):
    ai_session, character = await _session_and_character(session)
    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Пакет",
        actions=[
            {
                "name": "shakei_change",
                "arguments": {"character_id": character.id, "delta": 50},
                "description": "Начислить 50",
            },
            {
                "name": "character_set_stat",
                "arguments": {
                    "character_id": character.id,
                    "stat": "воля",
                    "value": 99,
                },
                "description": "Некорректный стат",
            },
        ],
        warnings=[],
    )

    with pytest.raises(ValidationError):
        await service.confirm_plan(
            session, plan_id=plan.id, admin_vk_id=500, peer_id=500
        )
    await session.refresh(character)
    assert character.shakei_balance == 0


@pytest.mark.asyncio
async def test_read_tool_loop_can_answer_without_creating_plan(session, monkeypatch):
    ai_session, character = await _session_and_character(session)
    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="read_tools",
                message="Ищу",
                tools=[
                    ai_service.AssistantToolCall(
                        name="get_character",
                        arguments={"character_id": character.id},
                    )
                ],
            ),
            ai_service.AdminAssistantTurn(
                kind="answer",
                message="У Авы 0 Шакеев.",
            ),
        ]
    )

    async def fake_turn(*_args, **_kwargs):
        return next(turns)

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    outcome = await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Сколько Шакеев у Авы?",
    )

    assert outcome.text == "У Авы 0 Шакеев."
    assert outcome.plan is None


@pytest.mark.asyncio
async def test_agent_recovers_from_typo_and_plans_card_creation_with_grant(
    session, monkeypatch
):
    character = await characters_crud.create(
        session, vk_id=100, name="Пикколо", is_approved=True
    )
    ai_session = await service.open_session(
        session, admin_vk_id=500, peer_id=500
    )
    calls = []
    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="read_tools",
                message="Ищу персонажа",
                tools=[
                    ai_service.AssistantToolCall(
                        name="find_character", arguments={"query": "Полоко"}
                    )
                ],
            ),
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Нашёл Пикколо и подготовил карту.",
                actions=[
                    ai_service.AssistantAction(
                        name="card_create_and_grant",
                        arguments={
                            "character_id": character.id,
                            "name": "Перенос",
                            "card_type": "Заклинание",
                            "kind": "Заклинание",
                            "rarity": "H",
                            "description": "Переносит цель.",
                            "usage": "Активируется командой.",
                        },
                        description="Создать карту «Перенос» и выдать Пикколо",
                    )
                ],
            ),
        ]
    )

    async def fake_turn(history, **_kwargs):
        calls.append(history)
        return next(turns)

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    outcome = await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Придумай Перенос и дай Полоко, имя примерно такое",
    )

    assert outcome.plan is not None
    assert "close_matches" in str(calls[1])
    assert "Пикколо" in str(calls[1])

    plan, executed = await service.confirm_plan(
        session,
        plan_id=outcome.plan.id,
        admin_vk_id=500,
        peer_id=500,
    )
    card = await cards_crud.get_by_name(session, "Перенос")
    ownerships = await cards_crud.list_character_ownerships(session, character.id)

    assert executed is True
    assert plan.status == "executed"
    assert card is not None
    assert [item.card_id for item in ownerships] == [card.id]


@pytest.mark.asyncio
async def test_assistant_converts_markdown_to_vk_plain_text(session, monkeypatch):
    ai_session, _ = await _session_and_character(session)

    async def fake_turn(*_args, **_kwargs):
        return ai_service.AdminAssistantTurn(
            kind="answer",
            message=(
                "## Возможности\n"
                "- **Персонажи** и `карты`\n"
                "- [Документация](https://example.com)"
            ),
        )

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    outcome = await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Что ты умеешь?",
    )

    assert outcome.text == (
        "Возможности\n"
        "• Персонажи и карты\n"
        "• Документация — https://example.com"
    )


@pytest.mark.asyncio
async def test_agent_retries_unnecessary_card_clarification(session, monkeypatch):
    ai_session, _ = await _session_and_character(session)
    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="clarification",
                message=(
                    "Укажите редкость: Обычная, Необычная, Эпическая или "
                    "Легендарная, описание эффекта и нужна ли запись в реестре."
                ),
            ),
            ai_service.AdminAssistantTurn(
                kind="clarification",
                message="Какому персонажу выдать карту? Укажите имя или ID анкеты.",
            ),
        ]
    )
    calls = []

    async def fake_turn(history, **_kwargs):
        calls.append(history)
        return next(turns)

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    outcome = await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Придумай Карту Заклинаний «Перенос» и выдай её персонажу.",
    )

    assert outcome.text == "Какому персонажу выдать карту? Укажите имя или ID анкеты."
    assert len(calls) == 2
    assert "уточнение и ответь заново" in str(calls[1])


@pytest.mark.asyncio
async def test_model_action_is_only_saved_as_plan(session, monkeypatch):
    ai_session, character = await _session_and_character(session)

    async def fake_turn(*_args, **_kwargs):
        return ai_service.AdminAssistantTurn(
            kind="action_plan",
            message="Начислить Шакеи",
            actions=[
                ai_service.AssistantAction(
                    name="shakei_change",
                    arguments={"character_id": character.id, "delta": 25},
                    description="Начислить Аве 25 Шакеев",
                )
            ],
        )

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    outcome = await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Дай Аве 25 Шакеев",
    )

    assert outcome.plan is not None
    assert outcome.plan.status == "proposed"
    assert character.shakei_balance == 0


@pytest.mark.asyncio
async def test_active_session_resumes_and_new_task_gets_clean_session(session):
    first = await service.open_session(session, admin_vk_id=500, peer_id=500)
    resumed = await service.open_session(session, admin_vk_id=500, peer_id=500)
    assert resumed.id == first.id

    second = await service.start_new_session(
        session,
        session_id=first.id,
        admin_vk_id=500,
        peer_id=500,
    )
    assert second.id != first.id
    assert first.status == "closed"


@pytest.mark.asyncio
async def test_plan_cannot_be_confirmed_from_another_peer(session):
    ai_session, character = await _session_and_character(session)
    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Начислить",
        actions=[
            {
                "name": "shakei_change",
                "arguments": {"character_id": character.id, "delta": 5},
                "description": "Начислить 5",
            }
        ],
        warnings=[],
    )

    with pytest.raises(PermissionDenied):
        await service.confirm_plan(
            session, plan_id=plan.id, admin_vk_id=500, peer_id=999
        )
    assert character.shakei_balance == 0


@pytest.mark.asyncio
async def test_service_rechecks_admin_for_direct_calls(session, monkeypatch):
    def deny(_vk_id):
        raise PermissionDenied("Только администратор")

    monkeypatch.setattr(service.auth_service, "require_admin", deny)
    with pytest.raises(PermissionDenied):
        await service.open_session(session, admin_vk_id=123, peer_id=123)
