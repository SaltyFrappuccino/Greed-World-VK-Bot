from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.keyboards.admin_menu import admin_menu
from bot.keyboards.main_menu import main_menu
from bot.middlewares.auth import NotAdminRule
from bot.states import clear_state, state_dispenser

# Все хендлеры этого модуля живут только в личных сообщениях сообщества.
labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])
labeler.vbml_ignore_case = True

GREETING = """Жадный Мир на связи.

Здесь - анкета, реестр карт и Шакеи.
Кубик и быстрые команды (?!карта, ?!профиль, ?!кубик) работают в общей беседе."""


@labeler.message(payload={"cmd": "menu"})
@labeler.message(text=["начать", "меню", "старт", "start", "/menu"])
async def show_menu(message: Message, is_admin: bool = False, **_: object) -> None:
    await clear_state(message.peer_id)
    await message.answer(GREETING, keyboard=main_menu(is_admin))


@labeler.message(payload={"cmd": "cancel"})
async def cancel(message: Message, is_admin: bool = False, **_: object) -> None:
    current_state = await state_dispenser.get(message.peer_id)
    return_to_admin = bool(
        is_admin
        and current_state is not None
        and current_state.state.startswith("Admin")
    )
    await clear_state(message.peer_id)
    if return_to_admin:
        await message.answer("Отменено. Возвращаю в админ-панель.", keyboard=admin_menu())
    else:
        await message.answer("Отменено.", keyboard=main_menu(is_admin))


@labeler.message(NotAdminRule(), payload={"cmd": "admin"})
async def admin_denied(message: Message, **_: object) -> None:
    """Кнопка админки от пользователя без прав."""
    await message.answer("Админ-панель доступна только администраторам.", keyboard=main_menu(False))


# Отдельный лейблер: main.py грузит его последним, иначе fallback съедал бы
# сообщения, адресованные хендлерам других модулей.
fallback_labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False)])


@fallback_labeler.message()
async def fallback(message: Message, is_admin: bool = False, **_: object) -> None:
    await message.answer("Не понял. Вот меню:", keyboard=main_menu(is_admin))
