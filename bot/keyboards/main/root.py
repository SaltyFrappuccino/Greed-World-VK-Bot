from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import CardType, Character


def main_menu(is_admin: bool = False) -> str:
    """Главное меню ЛС. Админу добавляется вход в админ-панель."""
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(Text("Мои анкеты", payload={"cmd": "profile"}), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(
        Text("Реестр анкет", payload={"cmd": "character_registry"}),
        color=KeyboardButtonColor.SECONDARY,
    )
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


def profile_menu(character_id: int, *, is_admin: bool = False) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if is_admin:
        keyboard.add(
            Text(
                "Карты ГеймМастеров",
                payload={"cmd": "cards_page", "page": 0, "type": CardType.GM.name},
            ),
            color=KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
        keyboard.add(
            Text(
                "Редактировать анкету",
                payload={"cmd": "admin_character_edit_select", "id": character_id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.add(
            Text(
                "Удалить анкету",
                payload={"cmd": "admin_character_delete_select", "id": character_id},
            ),
            color=KeyboardButtonColor.NEGATIVE,
        )
        keyboard.row()
        keyboard.add(
            Text(
                "Шакеи",
                payload={"cmd": "admin_character_shakei", "id": character_id},
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
        keyboard.add(
            Text(
                "Прокачать Контуры +1",
                payload={
                    "cmd": "admin_character_contour_limit_up",
                    "id": character_id,
                },
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.add(
            Text(
                "Задать лимит Контуров",
                payload={
                    "cmd": "admin_character_contour_limit_set",
                    "id": character_id,
                },
            )
        )
        keyboard.row()
        keyboard.add(
            Text(
                "Свободный слот +1",
                payload={"cmd": "admin_character_free_slots_up", "id": character_id},
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.add(
            Text(
                "Задать Свободные слоты",
                payload={"cmd": "admin_character_free_slots_set", "id": character_id},
            )
        )
        keyboard.row()
    keyboard.add(
        Text(
            "Карты персонажа",
            payload={
                "cmd": "admin_character_cards" if is_admin else "my_cards",
                "id": character_id,
            },
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(
        Text("Контуры", payload={"cmd": "character_contours", "id": character_id}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(
        Text("Арты", payload={"cmd": "character_arts", "id": character_id}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.add(
        Text("Трофеи", payload={"cmd": "character_trophies", "id": character_id}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "Экспорт карт XLSX",
            payload={"cmd": "character_cards_export", "id": character_id},
        ),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text(
            "Экспорт анкеты XLSX",
            payload={"cmd": "character_profile_export", "id": character_id},
        ),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
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
