from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.admin_menu import back_to_admin
from bot.keyboards.main_menu import cancel
from bot.middlewares.auth import AdminRule
from bot.services import character_service
from bot.services.character_template_service import CHARACTER_TEMPLATE, parse_character_template
from bot.services.vk_service import resolve_user_id
from bot.services.errors import ServiceError, ValidationError
from bot.states import AdminCharacterState, AdminStatsState, clear_state, state_dispenser
from bot.utils.validators import parse_int, parse_rarity

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(payload={"cmd": "admin_character_add"})
async def start_character_add(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminCharacterState.OWNER)
    await message.answer(
        "Кому принадлежит анкета? Пришлите числовой VK ID, упоминание "
        "или любую ссылку на профиль, например vk.ru/sword_saint.",
        keyboard=cancel(),
    )


@labeler.message(state=AdminCharacterState.OWNER)
async def pick_character_owner(message: Message, **_: object) -> None:
    try:
        vk_id = await resolve_user_id(message.ctx_api, message.text)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return

    await state_dispenser.set(
        message.peer_id, AdminCharacterState.TEMPLATE, owner_vk_id=vk_id
    )
    await message.answer(CHARACTER_TEMPLATE, keyboard=cancel())


@labeler.message(state=AdminCharacterState.TEMPLATE)
async def save_character(message: Message, **_: object) -> None:
    owner_vk_id = message.state_peer.payload["owner_vk_id"]
    async with get_session() as session:
        try:
            fields = parse_character_template(message.text)
            name = str(fields.pop("name"))
            character = await character_service.create_character(
                session, vk_id=owner_vk_id, name=name, **fields
            )
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(
        f"Анкета «{character.name}» добавлена владельцу VK {owner_vk_id}.",
        keyboard=back_to_admin(),
    )


@labeler.message(payload={"cmd": "admin_stats"})
async def start_adjustment(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminStatsState.INPUT)
    await message.answer(
        "Пришлите одной строкой:\n\n"
        "имя персонажа | показатель | значение\n\n"
        "Показатели: стрессоустойчивость, речевой аппарат, чуйка, хребет, "
        "воля, нюх, рейтинг. Статы - от 1 до 5, рейтинг - от H до SS.\n\n"
        "Пример: Ава | чуйка | 5",
        keyboard=cancel(),
    )


@labeler.message(state=AdminStatsState.INPUT)
async def apply_adjustment(message: Message, **_: object) -> None:
    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 3:
        await message.answer(
            "Формат: имя персонажа | показатель | значение", keyboard=cancel()
        )
        return

    character_name, indicator, value_text = parts
    async with get_session() as session:
        try:
            character = await character_service.find_character(session, character_name)
            if indicator.lower() == "рейтинг":
                rating = parse_rarity(value_text)
                await character_service.set_rating(session, character.id, rating)
                result = f"рейтинг {rating.value}"
            else:
                value = parse_int(value_text, field="Значение стата")
                field = character_service.resolve_stat(indicator)
                await character_service.set_stat(session, character.id, field, value)
                result = f"{character_service.STAT_FIELDS[field]} {value}"
            name = character.name
        except (ServiceError, ValidationError) as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await clear_state(message.peer_id)
    await message.answer(f"У персонажа {name} установлено: {result}.", keyboard=back_to_admin())
