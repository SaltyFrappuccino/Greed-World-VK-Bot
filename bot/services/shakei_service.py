from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import characters as characters_crud
from bot.database.crud import shakei as shakei_crud
from bot.database.models import Character, ShakeiTransaction
from bot.services.errors import InsufficientFunds, NotFoundError, ValidationError


def _check_amount(amount: int) -> None:
    if amount <= 0:
        raise ValidationError("Сумма должна быть больше нуля.")


async def _require_character(
    session: AsyncSession, character_id: int, *, for_update: bool = False
) -> Character:
    getter = characters_crud.get_by_id_for_update if for_update else characters_crud.get_by_id
    character = await getter(session, character_id)
    if character is None:
        raise NotFoundError("Персонаж не найден.")
    return character


async def transfer(
    session: AsyncSession,
    *,
    from_character_id: int,
    to_character_id: int,
    amount: int,
    reason: str = "",
) -> ShakeiTransaction:
    """Перевод Шакеев между игроками."""
    _check_amount(amount)
    if from_character_id == to_character_id:
        raise ValidationError("Нельзя перевести Шакеи самому себе.")

    # Одинаковый порядок блокировок не даёт встречным переводам создать deadlock.
    locked: dict[int, Character] = {}
    for character_id in sorted((from_character_id, to_character_id)):
        locked[character_id] = await _require_character(
            session, character_id, for_update=True
        )
    sender = locked[from_character_id]
    recipient = locked[to_character_id]

    if sender.shakei_balance < amount:
        raise InsufficientFunds(
            f"На балансе {sender.shakei_balance} Шакеев, нужно {amount}."
        )

    sender.shakei_balance -= amount
    recipient.shakei_balance += amount

    return await shakei_crud.add_transaction(
        session,
        amount=amount,
        from_character_id=sender.id,
        to_character_id=recipient.id,
        reason=reason,
    )


async def grant(
    session: AsyncSession,
    *,
    character_id: int,
    amount: int,
    admin_vk_id: int,
    reason: str = "",
) -> ShakeiTransaction:
    """Начисление админом: Шакеи приходят извне, отправителя нет."""
    _check_amount(amount)
    character = await _require_character(session, character_id, for_update=True)
    character.shakei_balance += amount

    return await shakei_crud.add_transaction(
        session,
        amount=amount,
        to_character_id=character.id,
        reason=reason,
        admin_vk_id=admin_vk_id,
    )


async def deduct(
    session: AsyncSession,
    *,
    character_id: int,
    amount: int,
    admin_vk_id: int,
    reason: str = "",
    allow_negative: bool = False,
) -> ShakeiTransaction:
    """Списание админом: Шакеи уходят из игры, получателя нет."""
    _check_amount(amount)
    character = await _require_character(session, character_id, for_update=True)

    if not allow_negative and character.shakei_balance < amount:
        raise InsufficientFunds(
            f"У {character.name} на балансе {character.shakei_balance} Шакеев, "
            f"списать {amount} нельзя."
        )

    character.shakei_balance -= amount

    return await shakei_crud.add_transaction(
        session,
        amount=amount,
        from_character_id=character.id,
        reason=reason,
        admin_vk_id=admin_vk_id,
    )


async def calculate_balance(session: AsyncSession, character_id: int) -> int:
    """Баланс, посчитанный по логу транзакций - для сверки с хранимым полем."""
    incoming = await shakei_crud.sum_incoming(session, character_id)
    outgoing = await shakei_crud.sum_outgoing(session, character_id)
    return incoming - outgoing


async def audit_balance(session: AsyncSession, character_id: int) -> tuple[int, int]:
    """Вернуть (хранимый баланс, баланс по логу). Расходятся - значит, что-то сломалось."""
    character = await _require_character(session, character_id)
    return character.shakei_balance, await calculate_balance(session, character_id)


async def history(
    session: AsyncSession, character_id: int, limit: int = 10
) -> list[ShakeiTransaction]:
    return await shakei_crud.list_history(session, character_id, limit=limit)
