import pytest

from bot.handlers.dm.admin import panel
from bot.services.backup_service import DatabaseBackup


class _FakeUploader:
    def __init__(self, api, attachment_name):
        self.api = api
        self.attachment_name = attachment_name

    async def upload(self, data, **kwargs):
        assert data == b"sqlite-data"
        assert kwargs["peer_id"] == 123
        return "doc-1_2_key"


class _FakeMessage:
    peer_id = 123
    ctx_api = object()

    def __init__(self):
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


@pytest.mark.asyncio
async def test_backup_handler_uploads_database_as_vk_document(monkeypatch):
    async def fake_backup():
        return DatabaseBackup("backup.db", b"sqlite-data")

    monkeypatch.setattr(panel.backup_service, "create_database_backup", fake_backup)
    monkeypatch.setattr(panel, "DocMessagesUploader", _FakeUploader)
    message = _FakeMessage()

    await panel.create_database_backup(message)

    assert message.answers[-1][1]["attachment"] == "doc-1_2_key"
