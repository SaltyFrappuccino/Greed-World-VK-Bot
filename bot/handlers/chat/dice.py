from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.services import dice_service
from bot.services.errors import ServiceError

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=True)])
labeler.vbml_ignore_case = True


@labeler.message(text=["?!кубик", "?!кубик <args>", "?!куб", "?!куб <args>"])
async def dice_command(message: Message, args: str = "", **_: object) -> None:
    try:
        low, high = dice_service.parse_bounds(args)
        result = dice_service.roll(low, high)
    except ServiceError as error:
        await message.answer(str(error))
        return

    await message.answer(f"🎲 {result.value}  ({result.low}–{result.high})")
