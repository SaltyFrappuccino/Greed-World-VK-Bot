from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database.crud import character_arts as arts_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import CharacterArt
from bot.services import art_storage_service, auth_service
from bot.services.errors import NotFoundError, PermissionDenied, ValidationError


async def list_visible(
    session: AsyncSession,
    *,
    character_id: int,
    viewer_vk_id: int,
    is_admin: bool,
) -> list[CharacterArt]:
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    if not is_admin and character.vk_id != viewer_vk_id:
        raise PermissionDenied("Арты доступны только владельцу анкеты и администратору.")
    return await arts_crud.list_for_character(session, character_id)


async def add_from_vk(
    session: AsyncSession,
    *,
    character_id: int,
    source_url: str,
    vk_attachment: str | None,
    caption: str,
    admin_vk_id: int,
    make_primary: bool = False,
) -> CharacterArt:
    auth_service.require_admin(admin_vk_id)
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    count = await arts_crud.count_for_character(session, character_id)
    if count >= get_settings().character_art_max_per_character:
        raise ValidationError("У анкеты достигнут лимит количества артов.")
    stored = await art_storage_service.download_and_store(
        source_url,
        character_id=character_id,
        session=session.sync_session,
    )
    duplicate = await arts_crud.get_by_hash(session, character_id, stored.sha256)
    if duplicate is not None:
        art_storage_service.schedule_delete(session.sync_session, stored.storage_key)
        raise ValidationError(f"Этот арт уже прикреплён к анкете как #{duplicate.id}.")
    primary = make_primary or count == 0
    if primary:
        await arts_crud.clear_primary(session, character_id)
    return await arts_crud.add(
        session,
        character_id=character_id,
        storage_key=stored.storage_key,
        sha256=stored.sha256,
        mime_type=stored.mime_type,
        file_size=stored.file_size,
        width=stored.width,
        height=stored.height,
        caption=_caption(caption),
        is_primary=primary,
        vk_attachment=vk_attachment,
        created_by=admin_vk_id,
    )


async def set_primary(
    session: AsyncSession, *, art_id: int, admin_vk_id: int
) -> CharacterArt:
    auth_service.require_admin(admin_vk_id)
    art = await arts_crud.get_by_id_for_update(session, art_id)
    if art is None:
        raise NotFoundError("Арт не найден.")
    await characters_crud.get_by_id_for_update(session, art.character_id)
    await arts_crud.clear_primary(session, art.character_id)
    art.is_primary = True
    await session.flush()
    return art


async def update_caption(
    session: AsyncSession, *, art_id: int, caption: str, admin_vk_id: int
) -> CharacterArt:
    auth_service.require_admin(admin_vk_id)
    art = await arts_crud.get_by_id_for_update(session, art_id)
    if art is None:
        raise NotFoundError("Арт не найден.")
    art.caption = _caption(caption)
    await session.flush()
    return art


async def delete_art(
    session: AsyncSession, *, art_id: int, admin_vk_id: int
) -> tuple[int, str]:
    auth_service.require_admin(admin_vk_id)
    art = await arts_crud.get_by_id_for_update(session, art_id)
    if art is None:
        raise NotFoundError("Арт не найден.")
    character_id = art.character_id
    await characters_crud.get_by_id_for_update(session, character_id)
    storage_key = art.storage_key
    was_primary = art.is_primary
    await arts_crud.delete(session, art)
    if was_primary:
        remaining = await arts_crud.list_for_character(session, character_id)
        if remaining:
            remaining[0].is_primary = True
            await session.flush()
    art_storage_service.schedule_delete(session.sync_session, storage_key)
    return character_id, storage_key


async def queue_character_files_for_delete(
    session: AsyncSession, character_id: int
) -> None:
    for art in await arts_crud.list_for_character(session, character_id):
        art_storage_service.schedule_delete(session.sync_session, art.storage_key)


def _caption(value: str) -> str:
    caption = value.strip()
    if len(caption) > 500:
        raise ValidationError("Подпись арта не может быть длиннее 500 символов.")
    return caption
