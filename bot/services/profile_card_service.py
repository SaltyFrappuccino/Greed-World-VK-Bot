import asyncio
import hashlib
import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import character_arts as arts_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import contours as contours_crud
from bot.database.crud import profile_cards as profile_cards_crud
from bot.database.models import CardType, CharacterProfileCard
from bot.services import art_storage_service, profile_card_storage_service
from bot.services.errors import NotFoundError
from bot.services.profile_card_renderer import (
    RENDER_VERSION,
    ProfileCardData,
    render_profile_card,
)


@dataclass(frozen=True)
class ProfileCardResult:
    cache: CharacterProfileCard
    character_name: str
    reused: bool
    data: bytes | None


async def get_or_create(
    session: AsyncSession, character_id: int
) -> ProfileCardResult:
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    ownerships = await cards_crud.list_character_ownerships(session, character_id)
    contours = await contours_crud.list_for_character(session, character_id)
    primary_art = await arts_crud.get_primary(session, character_id)
    signature = _signature(character, ownerships, contours, primary_art)
    input_hash = hashlib.sha256(
        json.dumps(signature, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache = await profile_cards_crud.get_for_character_for_update(
        session, character_id
    )
    if (
        cache is not None
        and cache.input_hash == input_hash
        and profile_card_storage_service.exists(cache.storage_key)
    ):
        data = (
            None
            if cache.vk_attachment
            else profile_card_storage_service.read_bytes(cache.storage_key)
        )
        return ProfileCardResult(cache, character.name, True, data)

    art_bytes = (
        art_storage_service.read_bytes(primary_art.storage_key)
        if primary_art is not None
        else None
    )
    render_data = _render_data(character, ownerships, contours)
    png = await asyncio.to_thread(render_profile_card, render_data, art_bytes)
    storage_key, file_size = profile_card_storage_service.save_png(
        png,
        character_id=character_id,
        input_hash=input_hash,
        session=session.sync_session,
    )
    old_storage_key = cache.storage_key if cache is not None else None
    cache = await profile_cards_crud.upsert(
        session,
        character_id=character_id,
        input_hash=input_hash,
        storage_key=storage_key,
        file_size=file_size,
        width=1200,
        height=1600,
    )
    if old_storage_key and old_storage_key != storage_key:
        profile_card_storage_service.schedule_delete(
            session.sync_session, old_storage_key
        )
    return ProfileCardResult(cache, character.name, False, png)


async def remember_vk_attachment(
    session: AsyncSession,
    *,
    character_id: int,
    input_hash: str,
    attachment: str,
) -> None:
    cache = await profile_cards_crud.get_for_character_for_update(
        session, character_id
    )
    if cache is not None and cache.input_hash == input_hash:
        cache.vk_attachment = attachment
        await session.flush()


async def queue_character_file_for_delete(
    session: AsyncSession, character_id: int
) -> None:
    cache = await profile_cards_crud.get_for_character(session, character_id)
    if cache is not None:
        profile_card_storage_service.schedule_delete(
            session.sync_session, cache.storage_key
        )


def _render_data(character, ownerships, contours) -> ProfileCardData:
    counts = {card_type.value: 0 for card_type in CardType}
    for ownership in ownerships:
        counts[ownership.display_type.value] += 1
    return ProfileCardData(
        character_id=character.id,
        name=character.name,
        age=character.age,
        gender=character.gender,
        rating=character.overall_rating.value,
        shakei=character.shakei_balance,
        stats={
            "stress_resistance": character.stress_resistance,
            "speech": character.speech,
            "intuition": character.intuition,
            "spine": character.spine,
            "will": character.will,
            "scent": character.scent,
        },
        skills=_skills(character.skills),
        card_counts=counts,
        contours_used=len(contours),
        contour_limit=character.contour_limit,
    )


def _signature(character, ownerships, contours, primary_art) -> dict[str, object]:
    return {
        "renderer_version": RENDER_VERSION,
        "character": {
            column.name: _json_value(getattr(character, column.name))
            for column in character.__table__.columns
        },
        "primary_art": (
            {"id": primary_art.id, "sha256": primary_art.sha256}
            if primary_art is not None
            else None
        ),
        "ownerships": [
            {
                "id": item.id,
                "card_id": item.card_id,
                "name": item.display_name,
                "type": item.display_type.value,
                "kind": item.display_kind,
                "rarity": item.display_rarity.value,
                "bound": item.contour_component is not None,
            }
            for item in ownerships
        ],
        "contours": [
            {
                column.name: _json_value(getattr(contour, column.name))
                for column in contour.__table__.columns
            }
            | {"components": [item.card_ownership_id for item in contour.components]}
            for contour in contours
        ],
    }


def _skills(value: str) -> list[str]:
    normalized = value.replace("•", "\n").replace("➤", "\n")
    return [
        line.strip().lstrip("-—").strip()
        for line in normalized.splitlines()
        if line.strip().lstrip("-—").strip()
    ]


def _json_value(value: object) -> object:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
