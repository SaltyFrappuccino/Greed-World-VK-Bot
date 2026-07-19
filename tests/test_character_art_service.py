from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from bot.database.crud import character_arts as arts_crud
from bot.database.crud import characters as characters_crud
from bot.services import art_storage_service, character_art_service
from bot.services.art_storage_service import StoredArt
from bot.services.errors import PermissionDenied, ValidationError


@pytest.fixture
def allow_admin(monkeypatch):
    monkeypatch.setattr(
        character_art_service.auth_service, "require_admin", lambda _vk_id: None
    )
    monkeypatch.setattr(
        character_art_service,
        "get_settings",
        lambda: SimpleNamespace(character_art_max_per_character=50),
    )


@pytest.mark.asyncio
async def test_art_lifecycle_and_visibility(session, monkeypatch, allow_admin):
    character = await characters_crud.create(
        session, vk_id=100, name="Ава", is_approved=True
    )
    counter = 0

    async def fake_store(_url, *, character_id, session):
        nonlocal counter
        counter += 1
        return StoredArt(
            storage_key=f"characters/{character_id}/{counter}.jpg",
            sha256=str(counter).zfill(64),
            mime_type="image/jpeg",
            file_size=100,
            width=10,
            height=20,
        )

    monkeypatch.setattr(
        character_art_service.art_storage_service,
        "download_and_store",
        fake_store,
    )
    monkeypatch.setattr(
        character_art_service.art_storage_service,
        "schedule_delete",
        lambda *_args: None,
    )

    first = await character_art_service.add_from_vk(
        session,
        character_id=character.id,
        source_url="https://sun.userapi.com/1.jpg",
        vk_attachment="photo1_1",
        caption="Первый",
        admin_vk_id=500,
    )
    second = await character_art_service.add_from_vk(
        session,
        character_id=character.id,
        source_url="https://sun.userapi.com/2.jpg",
        vk_attachment="photo1_2",
        caption="Второй",
        admin_vk_id=500,
    )
    assert first.is_primary is True
    assert second.is_primary is False

    await character_art_service.set_primary(
        session, art_id=second.id, admin_vk_id=500
    )
    await session.refresh(first)
    assert first.is_primary is False
    assert second.is_primary is True

    visible = await character_art_service.list_visible(
        session,
        character_id=character.id,
        viewer_vk_id=100,
        is_admin=False,
    )
    assert [art.id for art in visible] == [second.id, first.id]
    with pytest.raises(PermissionDenied):
        await character_art_service.list_visible(
            session,
            character_id=character.id,
            viewer_vk_id=999,
            is_admin=False,
        )

    await character_art_service.delete_art(
        session, art_id=second.id, admin_vk_id=500
    )
    await session.refresh(first)
    assert first.is_primary is True


@pytest.mark.asyncio
async def test_duplicate_art_is_rejected(session, monkeypatch, allow_admin):
    character = await characters_crud.create(session, vk_id=100, name="Ава")
    stored = StoredArt(
        storage_key="characters/1/same.jpg",
        sha256="a" * 64,
        mime_type="image/jpeg",
        file_size=100,
        width=10,
        height=10,
    )

    async def fake_store(*_args, **_kwargs):
        return stored

    monkeypatch.setattr(
        character_art_service.art_storage_service, "download_and_store", fake_store
    )
    monkeypatch.setattr(
        character_art_service.art_storage_service,
        "schedule_delete",
        lambda *_args: None,
    )
    await character_art_service.add_from_vk(
        session,
        character_id=character.id,
        source_url="https://sun.userapi.com/a.jpg",
        vk_attachment=None,
        caption="",
        admin_vk_id=500,
    )
    with pytest.raises(ValidationError, match="уже прикреплён"):
        await character_art_service.add_from_vk(
            session,
            character_id=character.id,
            source_url="https://sun.userapi.com/a.jpg",
            vk_attachment=None,
            caption="",
            admin_vk_id=500,
        )


@pytest.mark.asyncio
async def test_local_storage_commit_delete_and_rollback(tmp_path, session, monkeypatch):
    settings = SimpleNamespace(
        character_art_storage_path=tmp_path / "arts",
        character_art_max_file_bytes=1024 * 1024,
        character_art_max_total_bytes=10 * 1024 * 1024,
    )
    monkeypatch.setattr(art_storage_service, "get_settings", lambda: settings)
    buffer = BytesIO()
    Image.new("RGB", (20, 30), "green").save(buffer, format="JPEG")

    stored = art_storage_service.store_bytes(
        buffer.getvalue(), character_id=7, session=session.sync_session
    )
    path = settings.character_art_storage_path / stored.storage_key
    assert path.is_file()
    assert (stored.width, stored.height, stored.mime_type) == (20, 30, "image/jpeg")
    await session.commit()
    assert path.is_file()

    art_storage_service.schedule_delete(session.sync_session, stored.storage_key)
    await session.rollback()
    assert path.is_file()

    art_storage_service.schedule_delete(session.sync_session, stored.storage_key)
    await session.commit()
    assert not path.exists()


@pytest.mark.asyncio
async def test_local_storage_rejects_non_image(tmp_path, session, monkeypatch):
    settings = SimpleNamespace(
        character_art_storage_path=tmp_path / "arts",
        character_art_max_file_bytes=1024 * 1024,
        character_art_max_total_bytes=10 * 1024 * 1024,
    )
    monkeypatch.setattr(art_storage_service, "get_settings", lambda: settings)
    with pytest.raises(ValidationError, match="изображением"):
        art_storage_service.store_bytes(
            b"not an image", character_id=1, session=session.sync_session
        )


@pytest.mark.asyncio
async def test_primary_query(session):
    character = await characters_crud.create(session, vk_id=100, name="Ава")
    art = await arts_crud.add(
        session,
        character_id=character.id,
        storage_key="characters/1/a.jpg",
        sha256="b" * 64,
        mime_type="image/jpeg",
        file_size=100,
        width=10,
        height=10,
        caption="",
        is_primary=True,
        vk_attachment="photo1_1",
        created_by=500,
    )
    assert await arts_crud.get_primary(session, character.id) is art
