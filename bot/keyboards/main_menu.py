from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import Character


def main_menu(is_admin: bool = False) -> str:
    """Главное меню ЛС. Админу добавляется вход в админ-панель."""
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(Text("Мои анкеты", payload={"cmd": "profile"}), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Реестр карт", payload={"cmd": "cards"}), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(
        Text("Перевести Шакеи", payload={"cmd": "transfer"}), color=KeyboardButtonColor.SECONDARY
    )

    if is_admin:
        keyboard.row()
        keyboard.add(Text("Админ-панель", payload={"cmd": "admin"}), color=KeyboardButtonColor.NEGATIVE)

    return keyboard.get_json()


def back_to_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def cancel() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def profile_menu(character_id: int, is_owner_editable: bool = True) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if is_owner_editable:
        keyboard.add(
            Text("Редактировать", payload={"cmd": "profile_edit", "id": character_id}),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
    keyboard.add(
        Text("Карты персонажа", payload={"cmd": "my_cards", "id": character_id}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def profile_edit_menu(character_id: int, can_edit_stats: bool = False) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "Характер",
            payload={"cmd": "edit_field", "field": "personality", "id": character_id},
        )
    )
    keyboard.add(
        Text(
            "Биография",
            payload={"cmd": "edit_field", "field": "biography", "id": character_id},
        )
    )
    keyboard.row()
    keyboard.add(
        Text("Возраст", payload={"cmd": "edit_field", "field": "age", "id": character_id})
    )
    if can_edit_stats:
        stat_buttons = (
            ("stress_resistance", "Стрессоустойчивость"),
            ("speech", "Речевой аппарат"),
            ("intuition", "Чуйка"),
            ("spine", "Хребет"),
            ("will", "Воля"),
            ("scent", "Нюх"),
        )
        for index, (field, title) in enumerate(stat_buttons):
            if index % 2 == 0:
                keyboard.row()
            keyboard.add(
                Text(
                    title,
                    payload={"cmd": "edit_field", "field": field, "id": character_id},
                )
            )
    keyboard.row()
    keyboard.add(
        Text("К анкете", payload={"cmd": "profile_select", "id": character_id}),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def character_select_menu(command: str, characters: list[Character]) -> str:
    """Выбор одной из анкет владельца для следующего действия."""
    keyboard = Keyboard(one_time=False, inline=False)
    for index, character in enumerate(characters[:18]):
        if index and index % 2 == 0:
            keyboard.row()
        keyboard.add(
            Text(
                str(character.name),
                payload={"cmd": command, "id": int(character.id)},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()
