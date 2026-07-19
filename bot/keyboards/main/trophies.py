from vkbottle import Keyboard, KeyboardButtonColor, Text


def character_trophies_menu(character_id: int, *, is_admin: bool) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if is_admin:
        keyboard.add(
            Text(
                "Выдать трофей",
                payload={"cmd": "admin_trophy_award", "id": character_id},
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
    keyboard.add(
        Text(
            "К анкете",
            payload={"cmd": "character_registry_view", "id": character_id, "page": 0},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(
        Text("В меню", payload={"cmd": "menu"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()
