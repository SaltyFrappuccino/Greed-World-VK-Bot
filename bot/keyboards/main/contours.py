from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import Contour
from bot.keyboards.main.shared import _add_page_navigation, _short_label


def character_contours_menu(
    character_id: int,
    slots: list[tuple[int, Contour | None]],
    page: int,
    pages: int,
    *,
    is_admin: bool,
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for slot, contour in slots:
        if contour is not None:
            keyboard.add(
                Text(
                    _short_label(f"{slot}. {contour.name} ({len(contour.components)}/{contour.card_capacity})"),
                    payload={"cmd": "character_contour_view", "id": contour.id},
                ),
                color=KeyboardButtonColor.PRIMARY,
            )
        elif is_admin:
            keyboard.add(
                Text(
                    f"{slot}. Пустой слот — создать",
                    payload={
                        "cmd": "admin_contour_create",
                        "character_id": character_id,
                        "slot": slot,
                    },
                ),
                color=KeyboardButtonColor.POSITIVE,
            )
        else:
            continue
        keyboard.row()
    if page > 0:
        keyboard.add(
            Text(
                "←",
                payload={
                    "cmd": "character_contours_page",
                    "id": character_id,
                    "page": page - 1,
                },
            )
        )
    keyboard.add(
        Text(
            f"Страница {page + 1}/{pages}",
            payload={
                "cmd": "character_contours_page",
                "id": character_id,
                "page": page,
            },
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    if page + 1 < pages:
        keyboard.add(
            Text(
                "→",
                payload={
                    "cmd": "character_contours_page",
                    "id": character_id,
                    "page": page + 1,
                },
            )
        )
    keyboard.row()
    keyboard.add(
        Text(
            "К анкете",
            payload={
                "cmd": "character_registry_view" if is_admin else "profile_select",
                "id": character_id,
                "page": 0,
            },
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def contour_detail_menu(contour: Contour, *, is_admin: bool) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if is_admin:
        if contour.card_capacity < 5:
            keyboard.add(
                Text(
                    "Прокачать размер +1",
                    payload={"cmd": "admin_contour_capacity_up", "id": contour.id},
                ),
                color=KeyboardButtonColor.POSITIVE,
            )
        keyboard.add(
            Text(
                "Задать размер",
                payload={"cmd": "admin_contour_capacity_set", "id": contour.id},
            )
        )
        keyboard.row()
        keyboard.add(
            Text(
                "Изменить состав",
                payload={"cmd": "admin_contour_components", "id": contour.id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.add(
            Text(
                "Редактировать поля",
                payload={"cmd": "admin_contour_fields", "id": contour.id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
        keyboard.add(
            Text(
                "Переработать через AI",
                payload={"cmd": "admin_contour_ai", "id": contour.id},
            )
        )
        keyboard.row()
        keyboard.add(
            Text(
                "Разобрать Контур",
                payload={"cmd": "admin_contour_delete", "id": contour.id},
            ),
            color=KeyboardButtonColor.NEGATIVE,
        )
        keyboard.row()
    keyboard.add(
        Text(
            "К Контурам",
            payload={"cmd": "character_contours", "id": contour.character_id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


