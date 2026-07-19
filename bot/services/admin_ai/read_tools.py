from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import character_arts as arts_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import contours as contours_crud
from bot.database.models import Card, Character
from bot.services import (
    art_storage_service,
    backup_service,
    card_service,
    character_service,
    database_query_service,
    shakei_service,
    spreadsheet_service,
)
from bot.services.admin_ai.runtime import AssistantAttachment
from bot.services.admin_ai.values import (
    _card,
    _card_data,
    _card_type,
    _character,
    _character_data,
    _integer,
    _text,
)
from bot.services.errors import ServiceError, ValidationError

READ_TOOLS = {
    "find_character", "list_characters", "get_character",
    "find_card", "list_cards", "get_card", "get_shakei_history",
    "query_database", "export_character", "export_character_cards",
    "export_registry", "create_backup",
}

async def _run_read_tool(
    session: AsyncSession, name: str, arguments: dict[str, object]
) -> tuple[object, AssistantAttachment | None]:
    if name not in READ_TOOLS:
        raise ValidationError(f"AI запросил неизвестный read-инструмент: {name}.")
    if name == "find_character":
        return _character_data(await character_service.find_character(session, _text(arguments, "query"))), None
    if name == "list_characters":
        owner = arguments.get("owner_vk_id")
        query = str(arguments.get("query", "")).strip()
        if owner is not None:
            items = await characters_crud.list_by_vk_id(session, int(owner))
        elif query:
            items = await characters_crud.search_by_name(session, query, limit=20)
        else:
            items = await characters_crud.list_characters(session, limit=20, approved_only=False)
        return [_character_data(item) for item in items], None
    if name == "get_character":
        character = await _character(session, _integer(arguments, "character_id"))
        ownerships = await cards_crud.list_character_ownerships(session, character.id)
        contours = await contours_crud.list_for_character(session, character.id)
        data = _character_data(character)
        data["cards"] = [
            {"ownership_id": item.id, "name": item.display_name, "type": item.display_type.value, "bound": item.contour_component is not None}
            for item in ownerships
        ]
        stacks: dict[tuple[str, str, object], dict[str, object]] = {}
        for item in ownerships:
            key = (
                item.display_type.value,
                item.display_name.casefold(),
                item.card_id,
            )
            stack = stacks.setdefault(
                key,
                {
                    "card_id": item.card_id,
                    "name": item.display_name,
                    "type": item.display_type.value,
                    "total": 0,
                    "free": 0,
                    "bound": 0,
                },
            )
            stack["total"] = int(stack["total"]) + 1
            field = "bound" if item.contour_component is not None else "free"
            stack[field] = int(stack[field]) + 1
        data["card_stacks"] = list(stacks.values())
        data["contours"] = [
            {"id": item.id, "slot": item.slot, "name": item.name, "capacity": item.card_capacity, "components": [component.card_ownership_id for component in item.components]}
            for item in contours
        ]
        arts = await arts_crud.list_for_character(session, character.id)
        data["arts"] = [
            {
                "id": art.id,
                "caption": art.caption,
                "is_primary": art.is_primary,
                "mime_type": art.mime_type,
                "width": art.width,
                "height": art.height,
                "file_size": art.file_size,
            }
            for art in arts
        ]
        primary_art = next((art for art in arts if art.is_primary), None)
        attachment = None
        if primary_art is not None:
            extension = ".png" if primary_art.mime_type == "image/png" else ".jpg"
            attachment = AssistantAttachment(
                filename=f"character_{character.id}_primary_art{extension}",
                data=art_storage_service.read_bytes(primary_art.storage_key),
                kind="photo",
            )
        return data, attachment
    if name == "find_card":
        return _card_data(await card_service.find_card(session, _text(arguments, "query"))), None
    if name == "list_cards":
        items = await cards_crud.list_cards(session, limit=50)
        query = str(arguments.get("query", "")).strip().casefold()
        card_type = str(arguments.get("card_type", "")).strip()
        if query:
            items = [item for item in items if query in item.name.casefold()]
        if card_type:
            expected = _card_type(card_type)
            items = [item for item in items if item.card_type is expected]
        return [_card_data(item) for item in items], None
    if name == "get_card":
        card = await _card(session, _integer(arguments, "card_id"))
        data = _card_data(card)
        ownerships = await cards_crud.list_card_ownerships(session, card.id)
        data["live_copies"] = len(ownerships)
        data["owners"] = [
            {
                "ownership_id": item.id,
                "character_id": item.character_id,
                "character_name": item.character.name,
                "bound_contour_id": (
                    item.contour_component.contour_id
                    if item.contour_component is not None
                    else None
                ),
            }
            for item in ownerships
        ]
        return data, None
    if name == "get_shakei_history":
        character_id = _integer(arguments, "character_id")
        await _character(session, character_id)
        items = await shakei_service.history(session, character_id, limit=20)
        return [{"amount": item.amount, "from": item.from_character_id, "to": item.to_character_id, "created_at": str(item.created_at)} for item in items], None
    if name == "query_database":
        return await database_query_service.query_database(session, arguments), None
    if name == "export_character":
        export = await spreadsheet_service.export_character_profile(session, _integer(arguments, "character_id"))
    elif name == "export_character_cards":
        export = await spreadsheet_service.export_character_cards(session, _integer(arguments, "character_id"))
    elif name == "export_registry":
        export = await spreadsheet_service.export_registry(session)
    else:
        backup = await backup_service.create_database_backup()
        return {"filename": backup.filename, "ready": True}, AssistantAttachment(backup.filename, backup.data)
    return {"filename": export.filename, "ready": True}, AssistantAttachment(export.filename, export.data)


async def _failed_read_observation(
    session: AsyncSession,
    name: str,
    arguments: dict[str, object],
    error: ServiceError,
) -> dict[str, object]:
    observation: dict[str, object] = {
        "tool": name,
        "ok": False,
        "error": str(error),
        "instruction": "Это наблюдение, а не окончательный ответ. Попробуй другой read-инструмент или запрос.",
    }
    query = str(arguments.get("query", "")).strip()
    if not query:
        return observation
    if name == "find_character":
        candidates = await characters_crud.list_characters(
            session, limit=100, approved_only=False
        )
        suggestions = _closest_named(query, candidates)
        if suggestions:
            observation["close_matches"] = [
                {"id": item.id, "name": item.name, "vk_id": item.vk_id}
                for item in suggestions
            ]
    elif name == "find_card":
        candidates = await cards_crud.list_cards(session, limit=100)
        suggestions = _closest_named(query, candidates)
        if suggestions:
            observation["close_matches"] = [
                {"id": item.id, "name": item.name, "card_type": item.card_type.value}
                for item in suggestions
            ]
    return observation


def _closest_named(query: str, items: list[Character] | list[Card]) -> list[Character] | list[Card]:
    expected = query.casefold()
    ranked = sorted(
        (
            (SequenceMatcher(None, expected, item.name.casefold()).ratio(), item)
            for item in items
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [item for score, item in ranked[:5] if score >= 0.35]
