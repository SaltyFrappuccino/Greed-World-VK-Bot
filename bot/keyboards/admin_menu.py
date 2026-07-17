from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import CardType


def admin_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(Text("Добавить карту", payload={"cmd": "admin_card_add"}), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Редактировать карту", payload={"cmd": "admin_card_edit"}))
    keyboard.row()
    keyboard.add(Text("Удалить карту", payload={"cmd": "admin_card_delete"}), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("Начислить Шакеи", payload={"cmd": "admin_shakei"}), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Статы и рейтинг", payload={"cmd": "admin_stats"}))
    keyboard.row()
    keyboard.add(
        Text("Добавить анкету", payload={"cmd": "admin_character_add"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(Text("AI → Анкета", payload={"cmd": "admin_ai_character"}))
    keyboard.add(Text("AI → Контур", payload={"cmd": "admin_ai_contour"}))
    keyboard.row()
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def shakei_action_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(Text("Начислить", payload={"cmd": "admin_shakei_grant"}), color=KeyboardButtonColor.POSITIVE)
    keyboard.row()
    keyboard.add(Text("Списать", payload={"cmd": "admin_shakei_deduct"}), color=KeyboardButtonColor.NEGATIVE)
    keyboard.row()
    keyboard.add(Text("Назад", payload={"cmd": "admin"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def card_type_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for index, card_type in enumerate(CardType):
        if index and index % 2 == 0:
            keyboard.row()
        keyboard.add(
            Text(
                card_type.value,
                payload={"cmd": "admin_card_type", "type": card_type.name},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def back_to_admin() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(Text("В админ-панель", payload={"cmd": "admin"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def confirm_menu(action: str, target_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Подтвердить", payload={"cmd": f"{action}_confirm", "id": target_id}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "admin"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def ai_confirm_menu(action: str) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Сохранить", payload={"cmd": f"{action}_confirm"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def ai_collect_menu(action: str) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Готово — обработать", payload={"cmd": f"{action}_generate"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()
