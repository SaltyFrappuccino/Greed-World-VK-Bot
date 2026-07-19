import pytest
from types import SimpleNamespace

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import CharacterArt
from bot.services import ai_service
from bot.services import admin_ai_assistant_service as service
from bot.services.admin_ai import read_tools, write_tools
from bot.services.errors import ValidationError
from bot.services.errors import PermissionDenied
from bot.services.vk_discussion_service import (
    DiscussionApplication,
    DiscussionPhoto,
)


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
async def test_character_creation_can_atomically_attach_current_image(
    session, monkeypatch
):
    ai_session = await service.open_session(
        session, admin_vk_id=500, peer_id=500
    )
    attached: list[dict[str, object]] = []

    async def fake_add_from_vk(_session, **kwargs):
        attached.append(kwargs)
        return SimpleNamespace(id=91, character_id=kwargs["character_id"])

    monkeypatch.setattr(
        write_tools.character_art_service, "add_from_vk", fake_add_from_vk
    )
    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Создать анкету Пикколо с приложенным артом",
        actions=[
            {
                "name": "character_create",
                "arguments": {
                    "vk_id": 485208149,
                    "name": "Пикколо",
                    "fields": {"age": "31", "appearance": "По приложенному арту."},
                    "arts": [
                        {
                            "source_url": "https://sun.userapi.com/piccolo.jpg",
                            "caption": "Основной арт",
                            "make_primary": True,
                        }
                    ],
                },
                "description": "Создать анкету и прикрепить основной арт",
            }
        ],
        warnings=[],
    )

    executed, done = await service.confirm_plan(
        session, plan_id=plan.id, admin_vk_id=500, peer_id=500
    )

    characters = await characters_crud.list_by_vk_id(session, 485208149)
    assert done is True
    assert executed.status == "executed"
    assert [(item.name, item.vk_id) for item in characters] == [
        ("Пикколо", 485208149)
    ]
    assert attached == [
        {
            "character_id": characters[0].id,
            "source_url": "https://sun.userapi.com/piccolo.jpg",
            "vk_attachment": None,
            "caption": "Основной арт",
            "admin_vk_id": 500,
            "make_primary": True,
        }
    ]


@pytest.mark.asyncio
async def test_discussion_import_is_planned_then_creates_approved_character(
    session, monkeypatch
):
    ai_session = await service.open_session(
        session, admin_vk_id=500, peer_id=500
    )
    application = DiscussionApplication(
        group_id=240214251,
        topic_id=68811646,
        comment_id=77,
        author_vk_id=485208149,
        author_name="Слава Игрок",
        author_screen_name="slava",
        text="Анкета Пикколо",
        created_at=123,
        photos=(
            DiscussionPhoto(
                url="https://sun.userapi.com/piccolo.jpg",
                attachment="photo485208149_9_key",
                width=900,
                height=1400,
            ),
        ),
        content_hash="a" * 64,
    )

    async def fake_get_application(_comment_id):
        return application

    added_arts = []

    async def fake_add_from_vk(_session, **kwargs):
        added_arts.append(kwargs)
        return SimpleNamespace(id=91, character_id=kwargs["character_id"])

    monkeypatch.setattr(
        write_tools.vk_discussion_service,
        "get_application",
        fake_get_application,
    )
    monkeypatch.setattr(
        write_tools.character_art_service,
        "add_from_vk",
        fake_add_from_vk,
    )

    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Импортировать Пикколо из обсуждения",
        actions=[
            {
                "name": "character_import_discussion",
                "arguments": {
                    "comment_id": 77,
                    "name": "Пикколо",
                    "fields": {
                        "age": 31,
                        "gender": "Мужской",
                        "stress_resistance": 4,
                        "speech": 3,
                        "intuition": 4,
                        "spine": 5,
                        "will": 3,
                        "scent": 3,
                    },
                    "include_photos": True,
                },
                "description": "Импортировать анкету и основной арт",
            }
        ],
        warnings=[],
    )

    assert await characters_crud.get_by_discussion_source(
        session,
        group_id=240214251,
        topic_id=68811646,
        comment_id=77,
    ) is None

    executed, done = await service.confirm_plan(
        session, plan_id=plan.id, admin_vk_id=500, peer_id=500
    )

    character = await characters_crud.get_by_discussion_source(
        session,
        group_id=240214251,
        topic_id=68811646,
        comment_id=77,
    )
    assert done is True
    assert executed.status == "executed"
    assert character is not None
    assert character.name == "Пикколо"
    assert character.vk_id == 485208149
    assert character.is_approved is True
    assert character.source_comment_hash == "a" * 64
    assert added_arts[0]["vk_attachment"] == "photo485208149_9_key"
    assert added_arts[0]["make_primary"] is True


@pytest.mark.asyncio
async def test_existing_character_can_be_linked_without_duplicate(session, monkeypatch):
    ai_session, character = await _session_and_character(session)
    application = DiscussionApplication(
        group_id=240214251,
        topic_id=68811646,
        comment_id=88,
        author_vk_id=character.vk_id,
        author_name="Слава Игрок",
        author_screen_name="slava",
        text="Анкета Авы",
        created_at=123,
        photos=(),
        content_hash="b" * 64,
    )

    async def fake_get_application(_comment_id):
        return application

    monkeypatch.setattr(
        write_tools.vk_discussion_service,
        "get_application",
        fake_get_application,
    )
    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Связать существующую анкету с обсуждением",
        actions=[
            {
                "name": "character_link_discussion",
                "arguments": {"character_id": character.id, "comment_id": 88},
                "description": "Связать Аву с исходным комментарием",
            }
        ],
        warnings=[],
    )

    await service.confirm_plan(
        session, plan_id=plan.id, admin_vk_id=500, peer_id=500
    )

    characters = await characters_crud.list_by_vk_id(session, character.vk_id)
    assert len(characters) == 1
    assert character.source_comment_id == 88
    assert character.source_comment_hash == "b" * 64


@pytest.mark.asyncio
async def test_character_plan_normalizes_template_sections_from_flash_model(session):
    ai_session = await service.open_session(
        session, admin_vk_id=500, peer_id=500
    )
    plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Создать анкету из заполненного шаблона",
        actions=[
            {
                "name": "character_create",
                "arguments": {
                    "vk_id": 485208149,
                    "name": "Пикколо",
                    "fields": {
                        "age": "31",
                        "gender": "Мужской",
                        "appearance": "Зелёный намекианец.",
                        "biography": "Воин с Земли.",
                        "skills": ["Отличный тактик", "Аурафарм кинг"],
                    },
                    "character": "Сдержанный и решительный.",
                    "stats": {
                        "Стрессоустойчивость": "4",
                        "Речевой аппарат": 3,
                        "Чуйка": 4,
                        "Хребет": 5,
                        "Воля": 3,
                        "Нюх": 3,
                    },
                    "weakness": "Привязанность к семье.",
                    "rating": "H",
                    "shakei": 0,
                },
                "description": "Создать Пикколо",
            }
        ],
        warnings=[],
    )

    arguments = plan.actions[0]["arguments"]
    fields = arguments["fields"]
    assert set(arguments) == {"vk_id", "name", "fields"}
    assert fields["personality"] == "Сдержанный и решительный."
    assert fields["overall_rating"] == "H"
    assert fields["stress_resistance"] == 4
    assert fields["speech"] == 3
    assert fields["intuition"] == 4
    assert fields["spine"] == 5
    assert fields["will"] == 3
    assert fields["scent"] == 3
    assert fields["skills"] == "Отличный тактик\nАурафарм кинг"
    assert fields["additional"] == "Слабость: Привязанность к семье."
    assert fields["is_approved"] is True


@pytest.mark.asyncio
async def test_get_character_returns_primary_art_as_photo(session, monkeypatch):
    character = await characters_crud.create(
        session, vk_id=100, name="Пикколо", is_approved=True
    )
    session.add(
        CharacterArt(
            character_id=character.id,
            storage_key="characters/1/art.jpg",
            sha256="a" * 64,
            mime_type="image/jpeg",
            file_size=123,
            width=900,
            height=1400,
            caption="Основной арт",
            is_primary=True,
            created_by=500,
        )
    )
    await session.flush()
    monkeypatch.setattr(
        read_tools.art_storage_service, "read_bytes", lambda _key: b"image-data"
    )

    data, attachment = await read_tools._run_read_tool(
        session, "get_character", {"character_id": character.id}
    )

    assert data["arts"][0]["is_primary"] is True
    assert attachment is not None
    assert attachment.kind == "photo"
    assert attachment.data == b"image-data"


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
async def test_ai_plan_grants_and_partially_revokes_card_quantity(session):
    ai_session, character = await _session_and_character(session)
    create_plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Создать три копии Заклинания",
        actions=[
            {
                "name": "card_create_and_grant",
                "arguments": {
                    "character_id": character.id,
                    "name": "Три искры",
                    "card_type": "Заклинание",
                    "kind": "Заклинание",
                    "rarity": "H",
                    "quantity": 3,
                },
                "description": "Создать и выдать три копии",
            }
        ],
        warnings=[],
    )
    await service.confirm_plan(
        session, plan_id=create_plan.id, admin_vk_id=500, peer_id=500
    )
    card = await cards_crud.get_by_name(session, "Три искры")
    assert card is not None
    assert len(await cards_crud.list_character_ownerships(session, character.id)) == 3

    revoke_plan = await service.create_plan(
        session,
        ai_session=ai_session,
        admin_vk_id=500,
        summary="Забрать две копии",
        actions=[
            {
                "name": "card_revoke",
                "arguments": {
                    "character_id": character.id,
                    "card_id": card.id,
                    "quantity": 2,
                },
                "description": "Забрать две свободные копии",
            }
        ],
        warnings=[],
    )
    await service.confirm_plan(
        session, plan_id=revoke_plan.id, admin_vk_id=500, peer_id=500
    )
    assert len(await cards_crud.list_character_ownerships(session, character.id)) == 1


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
async def test_current_images_and_resolved_vk_context_survive_agent_rounds(
    session, monkeypatch
):
    ai_session, character = await _session_and_character(session)
    calls: list[tuple[list[dict[str, str]], list[str] | None]] = []
    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="read_tools",
                tools=[
                    ai_service.AssistantToolCall(
                        name="get_character",
                        arguments={"character_id": character.id},
                    )
                ],
            ),
            ai_service.AdminAssistantTurn(kind="answer", message="Готово."),
        ]
    )

    async def fake_turn(history, **kwargs):
        calls.append((history, kwargs.get("image_urls")))
        return next(turns)

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Посмотри арт владельца",
        image_urls=["https://sun.userapi.com/piccolo.jpg"],
        trusted_context=(
            "Проверено через VK API: vk.ru/piccolo → числовой VK ID 485208149"
        ),
    )

    assert len(calls) == 2
    assert calls[0][1] == ["https://sun.userapi.com/piccolo.jpg"]
    assert calls[1][1] == ["https://sun.userapi.com/piccolo.jpg"]
    assert "числовой VK ID 485208149" in str(calls[0][0])


@pytest.mark.asyncio
async def test_agent_repairs_text_vk_name_used_as_character_id(session, monkeypatch):
    ai_session = await service.open_session(
        session, admin_vk_id=500, peer_id=500
    )
    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Некорректный первый план",
                actions=[
                    ai_service.AssistantAction(
                        name="character_create",
                        arguments={"vk_id": 485208149, "name": "Пикколо"},
                    ),
                    ai_service.AssistantAction(
                        name="character_art_add",
                        arguments={
                            "character_id": "idi_nahuy_dayn_tupoi",
                            "image_index": 1,
                        },
                    ),
                ],
            ),
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Создать анкету вместе с артом",
                actions=[
                    ai_service.AssistantAction(
                        name="character_create",
                        arguments={
                            "vk_id": 485208149,
                            "name": "Пикколо",
                            "arts": [{"image_index": 1, "make_primary": True}],
                        },
                    )
                ],
            ),
        ]
    )
    histories = []

    async def fake_turn(history, **_kwargs):
        histories.append(history)
        return next(turns)

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    outcome = await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Создай анкету владельцу по короткой ссылке и прикрепи арт",
        image_urls=["https://sun.userapi.com/piccolo.jpg"],
        trusted_context="Числовой VK ID владельца: 485208149",
    )

    assert outcome.plan is not None
    arguments = outcome.plan.actions[0]["arguments"]
    assert arguments["vk_id"] == 485208149
    assert arguments["arts"][0]["source_url"].endswith("piccolo.jpg")
    assert "character_id.*целым числом" not in str(histories[0])
    assert "character_id должно быть целым числом" in str(histories[1])


@pytest.mark.asyncio
async def test_agent_recovers_from_read_tool_misuse_in_plan(session, monkeypatch):
    ai_session = await service.open_session(
        session, admin_vk_id=500, peer_id=500
    )
    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Сначала посмотрю данные",
                actions=[
                    ai_service.AssistantAction(
                        name="query_database",
                        arguments={"entity": "characters"},
                        description="Запросить данные из базы",
                    )
                ],
            ),
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Сначала посмотрю данные",
                actions=[
                    ai_service.AssistantAction(
                        name="query_database",
                        arguments={"entity": "characters"},
                        description="Запросить данные из базы",
                    )
                ],
            ),
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Создам анкету",
                actions=[
                    ai_service.AssistantAction(
                        name="character_create",
                        arguments={
                            "vk_id": 485208149,
                            "name": "Пикколо",
                        },
                        description="Создать анкету Пикколо",
                    )
                ],
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
        text="Создай анкету",
    )

    assert outcome.plan is not None
    assert outcome.plan.actions[0]["name"] == "character_create"


@pytest.mark.asyncio
async def test_agent_stops_after_same_invalid_plan_twice(session, monkeypatch):
    ai_session = await service.open_session(
        session, admin_vk_id=500, peer_id=500
    )

    async def invalid_turn(*_args, **_kwargs):
        return ai_service.AdminAssistantTurn(
            kind="action_plan",
            message="Некорректный план",
            actions=[
                ai_service.AssistantAction(
                    name="character_create",
                    arguments={
                        "vk_id": 485208149,
                        "name": "Пикколо",
                        "fields": {"alien_field": "не существует"},
                    },
                )
            ],
        )

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", invalid_turn)
    with pytest.raises(ValidationError, match="дважды предложил"):
        await service.process_message(
            session,
            session_id=ai_session.id,
            admin_vk_id=500,
            peer_id=500,
            text="Создай анкету",
        )


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
async def test_agent_can_use_previous_action_ownership_id_in_plan(session, monkeypatch):
    ai_session, character = await _session_and_character(session)

    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="План с привязкой только что выданной карты",
                actions=[
                    ai_service.AssistantAction(
                        name="card_create_and_grant",
                        arguments={
                            "character_id": character.id,
                            "name": "Снаряд",
                            "card_type": "Контурная",
                            "kind": "Снаряд",
                            "rarity": "B",
                            "description": "Контурная карта Снаряд.",
                            "usage": "Активируется в Контуре.",
                            "quantity": 1,
                        },
                        description="Создать и выдать карту Снаряд",
                    ),
                    ai_service.AssistantAction(
                        name="card_create_and_grant",
                        arguments={
                            "character_id": character.id,
                            "name": "Барьер",
                            "card_type": "Контурная",
                            "kind": "Барьер",
                            "rarity": "B",
                            "description": "Контурная карта Барьер.",
                            "usage": "Активируется в Контуре.",
                            "quantity": 1,
                        },
                        description="Создать и выдать карту Барьер",
                    ),
                    ai_service.AssistantAction(
                        name="contour_create",
                        arguments={
                            "character_id": character.id,
                            "ownership_ids": [
                                "$action_1.ownership_ids[0]",
                                "$action_2.ownership_ids[0]",
                            ],
                            "name": "Снарядный Хлеб",
                        },
                        description="Создать Контур с только что выданными картами",
                    ),
                ],
            )
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
        text="Собери Контур из только что выданной карты.",
    )

    assert outcome.plan is not None
    plan, executed = await service.confirm_plan(
        session,
        plan_id=outcome.plan.id,
        admin_vk_id=500,
        peer_id=500,
    )
    assert executed is True
    assert plan.status == "executed"


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


@pytest.mark.asyncio
async def test_plan_rejects_transform_limit_for_contour_card(session):
    ai_session, character = await _session_and_character(session)

    with pytest.raises(ValidationError, match="только для Особой"):
        await service.create_plan(
            session,
            ai_session=ai_session,
            admin_vk_id=500,
            summary="Некорректная Контурная карта",
            actions=[
                {
                    "name": "card_create_and_grant",
                    "arguments": {
                        "character_id": character.id,
                        "name": "Перенос",
                        "card_type": "Контурная",
                        "kind": "Форма — Область",
                        "rarity": "H",
                        "transform_limit": 3,
                    },
                    "description": "Создать и выдать карту",
                }
            ],
            warnings=[],
        )


@pytest.mark.asyncio
async def test_agent_repairs_rejected_card_plan_before_showing_it(session, monkeypatch):
    ai_session, character = await _session_and_character(session)
    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Первый план",
                actions=[
                    ai_service.AssistantAction(
                        name="card_create_and_grant",
                        arguments={
                            "character_id": character.id,
                            "name": "Перенос",
                            "card_type": "Контурная",
                            "kind": "Заклинание",
                            "rarity": "H",
                            "transform_limit": 3,
                        },
                        description="Некорректный план",
                    )
                ],
            ),
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Исправленный план",
                actions=[
                    ai_service.AssistantAction(
                        name="card_create_and_grant",
                        arguments={
                            "character_id": character.id,
                            "name": "Перенос",
                            "card_type": "Заклинание",
                            "kind": "Заклинание",
                            "rarity": "H",
                            "description": "Перемещает выбранную цель.",
                            "usage": "Активируется произнесением названия.",
                        },
                        description="Создать Карту Заклинаний и выдать Аве",
                    )
                ],
            ),
        ]
    )
    histories = []

    async def fake_turn(history, **_kwargs):
        histories.append(history)
        return next(turns)

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    outcome = await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Придумай карту Перенос и выдай Аве.",
    )

    assert outcome.plan is not None
    assert outcome.plan.summary == "Исправленный план"
    assert outcome.plan.actions[0]["arguments"]["card_type"] == "Заклинание"
    assert "transform_limit" not in outcome.plan.actions[0]["arguments"]
    assert "ПЛАН ОТКЛОНЁН" in str(histories[1])


@pytest.mark.asyncio
async def test_agent_repairs_character_stats_into_separate_actions(session, monkeypatch):
    ai_session, character = await _session_and_character(session)
    turns = iter(
        [
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Первый план",
                actions=[
                    ai_service.AssistantAction(
                        name="character_update",
                        arguments={
                            "character_id": character.id,
                            "fields": {
                                "biography": "Обновлённая биография",
                                "will": 4,
                                "scent": 5,
                            },
                        },
                    )
                ],
            ),
            ai_service.AdminAssistantTurn(
                kind="action_plan",
                message="Исправленный план",
                actions=[
                    ai_service.AssistantAction(
                        name="character_update",
                        arguments={
                            "character_id": character.id,
                            "fields": {"biography": "Обновлённая биография"},
                        },
                    ),
                    ai_service.AssistantAction(
                        name="character_set_stat",
                        arguments={"character_id": character.id, "stat": "will", "value": 4},
                    ),
                    ai_service.AssistantAction(
                        name="character_set_stat",
                        arguments={"character_id": character.id, "stat": "scent", "value": 5},
                    ),
                ],
            ),
        ]
    )
    histories = []

    async def fake_turn(history, **_kwargs):
        histories.append(history)
        return next(turns)

    monkeypatch.setattr(ai_service, "generate_admin_assistant_turn", fake_turn)
    outcome = await service.process_message(
        session,
        session_id=ai_session.id,
        admin_vk_id=500,
        peer_id=500,
        text="Обнови анкету по актуальной версии.",
    )

    assert outcome.plan is not None
    assert [action["name"] for action in outcome.plan.actions] == [
        "character_update",
        "character_set_stat",
        "character_set_stat",
    ]
    feedback = str(histories[1])
    assert "ПЛАН ОТКЛОНЁН" in feedback
    assert '"stat":"will","value":4' in feedback
    assert '"stat":"scent","value":5' in feedback
