from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import CardType, Contour, Rarity
from bot.services.card_template_service import CONTOUR_SUBTYPES



def admin_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Анкеты", payload={"cmd": "admin_characters"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.add(
        Text("Карты", payload={"cmd": "admin_cards"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    keyboard.add(
        Text("AI-Ассистент", payload={"cmd": "admin_ai_assistant"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Создать бэкап БД", payload={"cmd": "admin_database_backup"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def admin_ai_assistant_menu(session_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Новая задача", payload={"cmd": "admin_ai_assistant_new", "session_id": session_id}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text("Текущий план", payload={"cmd": "admin_ai_assistant_plan", "session_id": session_id}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    keyboard.add(
        Text("История", payload={"cmd": "admin_ai_assistant_history", "session_id": session_id}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(
        Text("Выйти из AI-режима", payload={"cmd": "admin_ai_assistant_exit", "session_id": session_id}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    return keyboard.get_json()


def admin_ai_plan_menu(plan_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Подтвердить", payload={"cmd": "admin_ai_plan_confirm", "plan_id": plan_id}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Изменить просьбу", payload={"cmd": "admin_ai_plan_revise", "plan_id": plan_id}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.add(
        Text("Отменить", payload={"cmd": "admin_ai_plan_cancel", "plan_id": plan_id}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    return keyboard.get_json()


def admin_ai_destructive_menu(plan_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Да, выполнить с удалением", payload={"cmd": "admin_ai_plan_destructive_confirm", "plan_id": plan_id}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Отменить план", payload={"cmd": "admin_ai_plan_cancel", "plan_id": plan_id}),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def admin_characters_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Добавить анкету", payload={"cmd": "admin_character_add_menu"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Выбрать существующую", payload={"cmd": "character_registry"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    keyboard.add(Text("Назад", payload={"cmd": "admin"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def admin_character_add_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Заполнить вручную", payload={"cmd": "admin_character_add"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(Text("Создать через AI", payload={"cmd": "admin_ai_character"}))
    keyboard.row()
    keyboard.add(
        Text("Назад", payload={"cmd": "admin_characters"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def admin_cards_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Добавить карту", payload={"cmd": "admin_card_add"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Выбрать существующую", payload={"cmd": "cards"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    keyboard.add(Text("Назад", payload={"cmd": "admin"}), color=KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def selected_shakei_action_menu(character_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "Начислить",
            payload={"cmd": "admin_character_shakei_grant", "id": character_id},
        ),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text(
            "Списать",
            payload={"cmd": "admin_character_shakei_deduct", "id": character_id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "К анкете",
            payload={"cmd": "character_registry_view", "id": character_id, "page": 0},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def cancel_character_shakei_menu(character_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "Отмена",
            payload={"cmd": "admin_character_shakei", "id": character_id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    return keyboard.get_json()

