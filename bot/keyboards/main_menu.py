from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import Card, Character, Contour


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


def card_registry_menu(
    cards: list[Card], page: int, pages: int, *, is_admin: bool = False
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for index, card in enumerate(cards):
        if index and index % 2 == 0:
            keyboard.row()
        keyboard.add(
            Text(
                _short_label(card.name),
                payload={"cmd": "card_registry_view", "id": card.id, "page": page},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
    if cards:
        keyboard.row()
    _add_page_navigation(keyboard, "cards_page", page, pages)
    keyboard.row()
    keyboard.add(Text("Поиск карты", payload={"cmd": "card_search"}))
    keyboard.add(
        Text(
            "К разделу «Карты»" if is_admin else "В меню",
            payload={"cmd": "admin_cards" if is_admin else "menu"},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def card_registry_detail_menu(
    card_id: int, page: int, *, is_admin: bool
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if is_admin:
        keyboard.add(
            Text(
                "Выдать карту",
                payload={"cmd": "admin_card_give", "id": card_id},
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.add(
            Text(
                "Владельцы",
                payload={"cmd": "admin_card_owners", "id": card_id},
            ),
            color=KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
        keyboard.add(
            Text(
                "Редактировать карту",
                payload={"cmd": "admin_card_edit_select", "id": card_id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.add(
            Text(
                "Удалить карту",
                payload={"cmd": "admin_card_delete_select", "id": card_id},
            ),
            color=KeyboardButtonColor.NEGATIVE,
        )
        keyboard.row()
    keyboard.add(
        Text("К реестру карт", payload={"cmd": "cards_page", "page": page}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "К разделу «Карты»" if is_admin else "В меню",
            payload={"cmd": "admin_cards" if is_admin else "menu"},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


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


def _add_page_navigation(
    keyboard: Keyboard, command: str, page: int, pages: int
) -> None:
    if page > 0:
        keyboard.add(Text("←", payload={"cmd": command, "page": page - 1}))
    keyboard.add(
        Text(
            f"Страница {page + 1}/{pages}",
            payload={"cmd": command, "page": page},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    if page + 1 < pages:
        keyboard.add(Text("→", payload={"cmd": command, "page": page + 1}))


def _short_label(text: str, limit: int = 36) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
