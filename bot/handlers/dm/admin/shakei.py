from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.admin_menu import back_to_admin, shakei_action_menu
from bot.keyboards.main_menu import cancel
from bot.middlewares.auth import AdminRule
from bot.services import character_service, shakei_service
from bot.services.errors import ServiceError
from bot.states import AdminShakeiState, clear_state, state_dispenser
from bot.utils.validators import parse_positive_int

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(payload={"cmd": "admin_shakei"})
async def choose_action(message: Message, **_: object) -> None:
    await clear_state(message.peer_id)
    await message.answer("Что сделать с Шакеями?", keyboard=shakei_action_menu())


@labeler.message(payload={"cmd": "admin_shakei_grant"})
async def start_grant(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminShakeiState.GRANT)
    await message.answer(
        "Начисление: имя персонажа | сумма | причина\n"
        "Пример: Ава | 100 | награда за задание",
        keyboard=cancel(),
    )


@labeler.message(payload={"cmd": "admin_shakei_deduct"})
async def start_deduct(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminShakeiState.DEDUCT)
    await message.answer(
        "Списание: имя персонажа | сумма | причина\n"
        "Пример: Ава | 25 | покупка карты",
        keyboard=cancel(),
    )


@labeler.message(state=AdminShakeiState.GRANT)
async def grant(message: Message, **_: object) -> None:
    await _apply(message, is_grant=True)


@labeler.message(state=AdminShakeiState.DEDUCT)
async def deduct(message: Message, **_: object) -> None:
    await _apply(message, is_grant=False)


async def _apply(message: Message, *, is_grant: bool) -> None:
    parts = [part.strip() for part in message.text.split("|", 2)]
    if len(parts) < 2:
        await message.answer("Формат: имя персонажа | сумма | причина", keyboard=cancel())
        return

    character_name, amount_text = parts[:2]
    reason = parts[2] if len(parts) == 3 else ""

    async with get_session() as session:
        try:
            amount = parse_positive_int(amount_text, field="Сумма")
            character = await character_service.find_character(session, character_name)
            if is_grant:
                await shakei_service.grant(
                    session,
                    character_id=character.id,
                    amount=amount,
                    admin_vk_id=message.from_id,
                    reason=reason,
                )
                action = "начислено"
            else:
                await shakei_service.deduct(
                    session,
                    character_id=character.id,
                    amount=amount,
                    admin_vk_id=message.from_id,
                    reason=reason,
                )
                action = "списано"
            name, balance = character.name, character.shakei_balance
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(
        f"Персонажу {name} {action} {amount} Шакеев. Баланс: {balance}.",
        keyboard=back_to_admin(),
    )
