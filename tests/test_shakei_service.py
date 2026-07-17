import pytest

from bot.database.crud import characters as characters_crud
from bot.services import shakei_service
from bot.services.errors import InsufficientFunds


@pytest.mark.asyncio
async def test_balance_matches_transaction_log(session):
    sender = await characters_crud.create(session, vk_id=1, name="Отправитель")
    recipient = await characters_crud.create(session, vk_id=2, name="Получатель")

    await shakei_service.grant(
        session, character_id=sender.id, amount=100, admin_vk_id=99, reason="старт"
    )
    await shakei_service.transfer(
        session,
        from_character_id=sender.id,
        to_character_id=recipient.id,
        amount=40,
        reason="сделка",
    )
    await shakei_service.deduct(
        session, character_id=recipient.id, amount=10, admin_vk_id=99, reason="покупка"
    )

    assert await shakei_service.audit_balance(session, sender.id) == (60, 60)
    assert await shakei_service.audit_balance(session, recipient.id) == (30, 30)


@pytest.mark.asyncio
async def test_transfer_rejects_insufficient_funds(session):
    sender = await characters_crud.create(session, vk_id=1, name="Бедный")
    recipient = await characters_crud.create(session, vk_id=2, name="Получатель")

    with pytest.raises(InsufficientFunds):
        await shakei_service.transfer(
            session,
            from_character_id=sender.id,
            to_character_id=recipient.id,
            amount=1,
        )

    assert sender.shakei_balance == 0
    assert recipient.shakei_balance == 0
