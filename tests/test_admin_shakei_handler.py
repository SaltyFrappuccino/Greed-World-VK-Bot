from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers.dm.admin import shakei


class _Message:
    peer_id = 123
    text = "75"
    state_peer = SimpleNamespace(
        payload={"character_id": 9, "character_name": "Ава", "is_grant": True}
    )


@pytest.mark.asyncio
async def test_amount_is_applied_immediately_without_reason_step(monkeypatch):
    message = _Message()
    apply_mock = AsyncMock()
    monkeypatch.setattr(shakei, "_apply", apply_mock)

    await shakei.save_amount(message)

    apply_mock.assert_awaited_once_with(
        message,
        {
            "character_id": 9,
            "character_name": "Ава",
            "is_grant": True,
            "amount": 75,
        },
    )
