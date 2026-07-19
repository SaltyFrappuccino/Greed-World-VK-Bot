from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import CardType, Rarity
from bot.services.card_template_service import CONTOUR_SUBTYPES


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


def card_add_mode_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Пошагово", payload={"cmd": "admin_card_add_wizard"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.add(
        Text("Шаблон целиком", payload={"cmd": "admin_card_add_template"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(
        Text("Оформить через AI", payload={"cmd": "admin_card_add_ai"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def card_rarity_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for index, rarity in enumerate(Rarity):
        if index and index % 5 == 0:
            keyboard.row()
        keyboard.add(
            Text(rarity.value, payload={"cmd": "admin_card_rarity", "rarity": rarity.name}),
            color=KeyboardButtonColor.PRIMARY,
        )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def contour_subtype_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for index, subtype in enumerate(CONTOUR_SUBTYPES):
        if index and index % 2 == 0:
            keyboard.row()
        keyboard.add(
            Text(subtype, payload={"cmd": "admin_card_contour_subtype", "subtype": subtype}),
            color=KeyboardButtonColor.PRIMARY,
        )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def special_card_limit_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    values: tuple[tuple[str, str | int], ...] = (
        ("Без лимита", "none"),
        ("1", 1),
        ("2", 2),
        ("3", 3),
        ("5", 5),
        ("10", 10),
    )
    for index, (label, value) in enumerate(values):
        if index and index % 3 == 0:
            keyboard.row()
        keyboard.add(
            Text(label, payload={"cmd": "admin_card_limit", "limit": value}),
            color=(
                KeyboardButtonColor.SECONDARY
                if value == "none"
                else KeyboardButtonColor.PRIMARY
            ),
        )
    keyboard.row()
    keyboard.add(Text("Другое число", payload={"cmd": "admin_card_limit_custom"}))
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def skip_card_field_menu(command: str) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Пропустить", payload={"cmd": command}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(Text("Отмена", payload={"cmd": "cancel"}), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def back_to_admin() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(Text("В админ-панель", payload={"cmd": "admin"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def back_to_admin_characters() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("К разделу «Анкеты»", payload={"cmd": "admin_characters"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def back_to_admin_cards() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("К разделу «Карты»", payload={"cmd": "admin_cards"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def confirm_menu(
    action: str,
    target_id: int,
    *,
    cancel_cmd: str = "admin",
    cancel_payload: dict[str, object] | None = None,
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Подтвердить", payload={"cmd": f"{action}_confirm", "id": target_id}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Отмена", payload=cancel_payload or {"cmd": cancel_cmd}),
        color=KeyboardButtonColor.SECONDARY,
    )
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


def card_owners_menu(card_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "Выдать ещё копию",
            payload={"cmd": "admin_card_give", "id": card_id},
        ),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "К карте",
            payload={"cmd": "card_registry_view", "id": card_id, "page": 0},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()
