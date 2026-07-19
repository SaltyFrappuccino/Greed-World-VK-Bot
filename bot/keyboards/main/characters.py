from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import Character
from bot.keyboards.main.shared import _add_page_navigation, _short_label


def character_registry_menu(
    characters: list[Character], page: int, pages: int, *, is_admin: bool = False
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for index, character in enumerate(characters):
        if index and index % 2 == 0:
            keyboard.row()
        keyboard.add(
            Text(
                _short_label(f"#{character.id} {character.name}"),
                payload={
                    "cmd": "character_registry_view",
                    "id": character.id,
                    "page": page,
                },
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
    if characters:
        keyboard.row()
    _add_page_navigation(keyboard, "character_registry_page", page, pages)
    keyboard.row()
    keyboard.add(
        Text(
            "К разделу «Анкеты»" if is_admin else "В меню",
            payload={"cmd": "admin_characters" if is_admin else "menu"},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def character_registry_detail_menu(
    character_id: int,
    page: int,
    *,
    is_admin: bool,
    can_view_contours: bool = False,
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "Трофеи",
            payload={"cmd": "character_trophies", "id": character_id},
        ),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    if is_admin:
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
                payload={"cmd": "admin_character_cards", "id": character_id},
            ),
            color=KeyboardButtonColor.SECONDARY,
        )
        keyboard.add(
            Text(
                "Контуры",
                payload={"cmd": "character_contours", "id": character_id},
            ),
            color=KeyboardButtonColor.SECONDARY,
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
    elif can_view_contours:
        keyboard.add(
            Text(
                "Контуры",
                payload={"cmd": "character_contours", "id": character_id},
            ),
            color=KeyboardButtonColor.SECONDARY,
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
    if is_admin or can_view_contours:
        keyboard.add(
            Text(
                "Арты",
                payload={"cmd": "character_arts", "id": character_id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
    keyboard.add(
        Text(
            "К реестру анкет",
            payload={"cmd": "character_registry_page", "page": page},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "К разделу «Анкеты»" if is_admin else "В меню",
            payload={"cmd": "admin_characters" if is_admin else "menu"},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()
