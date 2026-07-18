from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import Card, Character


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
        Text("Карты персонажа", payload={"cmd": "my_cards", "id": character_id}),
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


def card_registry_menu(cards: list[Card], page: int, pages: int) -> str:
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
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def card_registry_detail_menu(
    card_id: int, page: int, *, is_admin: bool
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if is_admin:
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
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def character_registry_menu(
    characters: list[Character], page: int, pages: int
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
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def character_registry_detail_menu(
    character_id: int,
    page: int,
    *,
    is_admin: bool,
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
            "К реестру анкет",
            payload={"cmd": "character_registry_page", "page": page},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
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
