import pytest

from bot.database.crud import characters as characters_crud
from bot.services import admin_ai_assistant_service, database_query_service
from bot.services.errors import ValidationError


@pytest.mark.asyncio
async def test_query_database_reads_current_filtered_rows(session):
    await characters_crud.create(
        session, vk_id=200, name="Бета", shakei_balance=10, is_approved=True
    )
    await characters_crud.create(
        session, vk_id=100, name="Альфа", shakei_balance=25, is_approved=True
    )

    result = await database_query_service.query_database(
        session,
        {
            "entity": "characters",
            "fields": ["id", "name", "vk_id", "shakei_balance", "overall_rating"],
            "filters": [
                {"field": "shakei_balance", "op": "gte", "value": 20},
                {"field": "overall_rating", "op": "eq", "value": "H"},
            ],
            "order_by": [{"field": "name", "direction": "asc"}],
            "limit": 10,
        },
    )

    assert result["returned"] == 1
    assert result["rows"][0]["name"] == "Альфа"
    assert result["rows"][0]["overall_rating"] == "H"


@pytest.mark.asyncio
async def test_query_database_supports_count(session):
    await characters_crud.create(session, vk_id=100, name="Альфа")
    await characters_crud.create(session, vk_id=200, name="Бета")

    result = await database_query_service.query_database(
        session,
        {
            "entity": "characters",
            "mode": "count",
            "filters": [{"field": "name", "op": "contains", "value": "а"}],
        },
    )

    assert result == {"entity": "characters", "mode": "count", "count": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"entity": "admin_ai_messages"}, "Неизвестная сущность"),
        (
            {"entity": "characters", "fields": ["password"]},
            "Неизвестные поля",
        ),
        (
            {"entity": "characters", "limit": 51},
            "limit должен быть от 1 до 50",
        ),
        (
            {
                "entity": "characters",
                "filters": [{"field": "name", "op": "raw_sql", "value": "1=1"}],
            },
            "Неизвестный оператор",
        ),
    ],
)
async def test_query_database_rejects_outside_whitelist(session, arguments, message):
    with pytest.raises(ValidationError, match=message):
        await database_query_service.query_database(session, arguments)


def test_query_database_is_registered_only_as_read_tool():
    assert "query_database" in admin_ai_assistant_service.READ_TOOLS
    assert "query_database" not in admin_ai_assistant_service.WRITE_TOOLS


@pytest.mark.asyncio
async def test_agent_read_dispatch_executes_database_query(session):
    await characters_crud.create(session, vk_id=100, name="Альфа")

    result, attachment = await admin_ai_assistant_service._run_read_tool(
        session,
        "query_database",
        {
            "entity": "characters",
            "fields": ["id", "name"],
            "filters": [{"field": "name", "op": "eq", "value": "Альфа"}],
        },
    )

    assert result["rows"][0]["name"] == "Альфа"
    assert attachment is None
