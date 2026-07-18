from bot.config import get_settings
from bot.services.errors import PermissionDenied


def require_admin(vk_id: int) -> None:
    """Повторная сервисная проверка для любой админской записи."""
    if not get_settings().is_admin(vk_id):
        raise PermissionDenied("Это действие доступно только администраторам.")
