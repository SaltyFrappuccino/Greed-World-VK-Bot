from typing import Any

from bot.services.errors import ValidationError
from bot.utils.validators import parse_vk_reference


async def resolve_user_id(api: Any, text: str) -> int:
    reference = parse_vk_reference(text)
    if isinstance(reference, int):
        return reference

    try:
        users = await api.users.get(user_ids=[reference])
    except Exception as error:
        raise ValidationError(
            "Не удалось проверить ссылку через VK API. Попробуйте числовой VK ID."
        ) from error
    if not users:
        raise ValidationError(f"Пользователь VK «{reference}» не найден.")
    return int(users[0].id)
