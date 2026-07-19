import re

from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.services import card_service, character_service
from bot.services.errors import ServiceError, ValidationError
from bot.utils.validators import extract_vk_id, parse_positive_int, strip_mentions

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=True)])
labeler.vbml_ignore_case = True

_CHARACTER_RE = re.compile(r"^#(\d+)\s+")
_QUANTITY_RE = re.compile(r"\s+[xх×](\d+)\s*$", re.IGNORECASE)

USAGE_HINT = (
    "Формат: ?использовать [#ID анкеты] Название карты [xКоличество] @игрок\n"
    "Например: ?использовать #12 Перенос x2 [id123|Слава]\n\n"
    "Если у вас одна анкета, её ID можно не указывать. Списываются только "
    "свободные Карты Заклинаний и Обычные карты; связанные с Контуром копии "
    "не затрагиваются."
)


@labeler.message(text=["?использовать", "?потратить"])
async def usage_without_arguments(message: Message, **_: object) -> None:
    await message.answer(USAGE_HINT)


@labeler.message(text=["?использовать <args>", "?потратить <args>"])
async def consume_card_command(message: Message, args: str, **_: object) -> None:
    try:
        character_id, card_name, quantity, target_vk_id = _parse_usage(
            message, args
        )
        async with get_session() as session:
            character = await _resolve_character(
                session,
                sender_vk_id=message.from_id,
                character_id=character_id,
            )
            result = await card_service.consume_card(
                session,
                character_id=character.id,
                used_by_vk_id=message.from_id,
                name=card_name,
                quantity=quantity,
                target_vk_id=target_vk_id,
                peer_id=message.peer_id,
                conversation_message_id=getattr(
                    message, "conversation_message_id", None
                ),
            )
    except ServiceError as error:
        await message.answer(str(error))
        return

    await message.answer(
        f"Карта использована и списана.\n"
        f"Персонаж: #{result.character_id} · {result.character_name}\n"
        f"Карта: {result.card_name} · {result.card_type.value}\n"
        f"Количество: {result.quantity}\n"
        f"Свободных копий осталось: {result.remaining_free}\n"
        f"Сцена с: [id{target_vk_id}|соигроком]\n"
        f"ID записи расхода: #{result.usage_id}"
    )


async def _resolve_character(session, *, sender_vk_id: int, character_id: int | None):
    if character_id is not None:
        return await character_service.require_owned(
            session, character_id=character_id, vk_id=sender_vk_id
        )
    characters = await character_service.list_by_vk_id(session, sender_vk_id)
    if not characters:
        raise ValidationError("У вас нет анкет.")
    if len(characters) > 1:
        choices = ", ".join(f"#{item.id} · {item.name}" for item in characters)
        raise ValidationError(
            f"У вас несколько анкет: {choices}. Укажите нужный ID после команды."
        )
    return characters[0]


def _parse_usage(
    message: Message, args: str
) -> tuple[int | None, str, int, int]:
    target_vk_id = extract_vk_id(args)
    if target_vk_id is None and message.reply_message is not None:
        target_vk_id = message.reply_message.from_id
    if target_vk_id is None:
        raise ValidationError("Упомяните соигрока или ответьте на его сообщение.")
    if target_vk_id <= 0:
        raise ValidationError("Целью использования должен быть VK-пользователь.")
    if target_vk_id == message.from_id:
        raise ValidationError("Укажите соигрока, а не самого себя.")

    text = strip_mentions(args).strip()
    character_id = None
    character_match = _CHARACTER_RE.match(text)
    if character_match:
        character_id = int(character_match.group(1))
        text = text[character_match.end() :].strip()

    quantity = 1
    quantity_match = _QUANTITY_RE.search(text)
    if quantity_match:
        quantity = parse_positive_int(
            quantity_match.group(1), field="Количество карт"
        )
        text = text[: quantity_match.start()].strip()
    if not text:
        raise ValidationError("Укажите точное название карты.")
    return character_id, text, quantity, target_vk_id
