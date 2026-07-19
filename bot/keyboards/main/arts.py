from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import CharacterArt


def character_arts_menu(
    character_id: int, arts: list[CharacterArt], *, is_admin: bool
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if is_admin:
        keyboard.add(
            Text(
                "Добавить арт",
                payload={"cmd": "admin_character_art_add", "id": character_id},
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
    for index, art in enumerate(arts[:18]):
        if index and index % 2 == 0:
            keyboard.row()
        title = f"#{art.id} {'★ ' if art.is_primary else ''}{art.caption or 'Без подписи'}"
        keyboard.add(
            Text(
                title[:40],
                payload={"cmd": "character_art_view", "id": art.id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
    if arts:
        keyboard.row()
    keyboard.add(
        Text(
            "К анкете",
            payload={"cmd": "character_registry_view", "id": character_id, "page": 0},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def character_art_detail_menu(art: CharacterArt, *, is_admin: bool) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if is_admin:
        if not art.is_primary:
            keyboard.add(
                Text(
                    "Сделать основным",
                    payload={"cmd": "admin_character_art_primary", "id": art.id},
                ),
                color=KeyboardButtonColor.POSITIVE,
            )
            keyboard.row()
        keyboard.add(
            Text(
                "Изменить подпись",
                payload={"cmd": "admin_character_art_caption", "id": art.id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.add(
            Text(
                "Удалить арт",
                payload={"cmd": "admin_character_art_delete", "id": art.id},
            ),
            color=KeyboardButtonColor.NEGATIVE,
        )
        keyboard.row()
    keyboard.add(
        Text(
            "К артам",
            payload={"cmd": "character_arts", "id": art.character_id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def character_art_delete_confirm_menu(art: CharacterArt) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "Да, удалить арт",
            payload={"cmd": "admin_character_art_delete_confirm", "id": art.id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "Отмена",
            payload={"cmd": "character_art_view", "id": art.id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()
