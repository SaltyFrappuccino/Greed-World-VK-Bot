from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.keyboards.main_menu import main_menu
from bot.middlewares.auth import NotAdminRule
from bot.services.errors import ServiceError
from bot.services.navigation_service import render_return
from bot.states import clear_state, return_context, state_dispenser

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True

GREETING = """Жадный Мир на связи.

Здесь - анкета, реестр карт и Шакеи.
Кубик и быстрые команды (?карта, ?профиль, ?кубик) работают в общей беседе."""


@labeler.message(payload={"cmd": "menu"})
@labeler.message(text=["начать", "меню", "старт", "start", "/menu"])
async def show_menu(message: Message, is_admin: bool = False, **_: object) -> None:
    await clear_state(message.peer_id)
    await message.answer(GREETING, keyboard=main_menu(is_admin))


@labeler.message(payload={"cmd": "cancel"})
async def cancel(message: Message, is_admin: bool = False, **_: object) -> None:
    current_state = await state_dispenser.get(message.peer_id)
    context = return_context(
        dict(current_state.payload) if current_state is not None else None
    )
    await clear_state(message.peer_id)
    try:
        await render_return(message, context, is_admin=is_admin)
    except ServiceError as error:
        await message.answer(
            f"Сценарий отменён, но прежний экран недоступен: {error}",
            keyboard=main_menu(is_admin),
        )


@labeler.message(NotAdminRule(), payload={"cmd": "admin"})
async def admin_denied(message: Message, **_: object) -> None:
    """Кнопка админки от пользователя без прав."""
    await message.answer("Админ-панель доступна только администраторам.", keyboard=main_menu(False))


fallback_labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])


@fallback_labeler.message()
async def fallback(message: Message, is_admin: bool = False, **_: object) -> None:
    await message.answer("Не понял. Вот меню:", keyboard=main_menu(is_admin))
