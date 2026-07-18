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
        Text("Создать бэкап БД", payload={"cmd": "admin_database_backup"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(Text("В меню", payload={"cmd": "menu"}), color=KeyboardButtonColor.SECONDARY)
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
    action: str, target_id: int, *, cancel_cmd: str = "admin"
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Подтвердить", payload={"cmd": f"{action}_confirm", "id": target_id}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Отмена", payload={"cmd": cancel_cmd}),
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


def admin_character_edit_menu(character_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    fields = (
        ("name", "Имя"),
        ("age", "Возраст"),
        ("gender", "Пол"),
        ("appearance", "Внешность"),
        ("personality", "Характер"),
        ("biography", "Биография"),
        ("skills", "Навыки"),
        ("additional", "Дополнительно"),
        ("stress_resistance", "Стрессоустойчивость"),
        ("speech", "Речевой аппарат"),
        ("intuition", "Чуйка"),
        ("spine", "Хребет"),
        ("will", "Воля"),
        ("scent", "Нюх"),
        ("overall_rating", "Рейтинг"),
        ("vk_id", "Владелец VK"),
    )
    for index, (field, title) in enumerate(fields):
        if index and index % 2 == 0:
            keyboard.row()
        keyboard.add(
            Text(
                title,
                payload={"cmd": "admin_character_edit_field", "id": character_id, "field": field},
            )
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


def contour_create_components_menu(
    cards: list[tuple[int, str, int]],
    *,
    selected_count: int,
    page: int,
    pages: int,
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for ownership_id, name, free_count in cards:
        keyboard.add(
            Text(
                _short_label(f"{name} · свободно {free_count}"),
                payload={
                    "cmd": "admin_contour_component_select",
                    "ownership_id": ownership_id,
                },
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
    _add_pager(keyboard, "admin_contour_components_create_page", page, pages)
    keyboard.row()
    if selected_count >= 2:
        keyboard.add(
            Text(
                f"Готово · выбрано {selected_count}",
                payload={"cmd": "admin_contour_components_ready"},
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
    keyboard.add(
        Text("Отмена", payload={"cmd": "cancel"}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    return keyboard.get_json()


def contour_create_mode_menu() -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text("Пошагово", payload={"cmd": "admin_contour_mode_manual"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.add(
        Text("Шаблон целиком", payload={"cmd": "admin_contour_mode_template"}),
        color=KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(Text("Через AI", payload={"cmd": "admin_contour_mode_ai"}))
    keyboard.row()
    keyboard.add(
        Text("Отмена", payload={"cmd": "cancel"}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    return keyboard.get_json()


def contour_fields_menu(contour_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    fields = (
        ("name", "Название"),
        ("appearance", "Внешний вид"),
        ("primary_effect", "Основной эффект"),
        ("additional_capabilities", "Доп. возможности"),
        ("activation_conditions", "Условия активации"),
        ("duration", "Продолжительность"),
        ("conductivity", "Проводимость"),
        ("overload_impact", "Перегрузка"),
    )
    for index, (field, title) in enumerate(fields):
        if index and index % 2 == 0:
            keyboard.row()
        keyboard.add(
            Text(
                title,
                payload={
                    "cmd": "admin_contour_field_select",
                    "id": contour_id,
                    "field": field,
                },
            )
        )
    keyboard.row()
    keyboard.add(
        Text(
            "К Контуру",
            payload={"cmd": "character_contour_view", "id": contour_id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def contour_components_actions_menu(contour: Contour) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    if not contour.components:
        keyboard.add(
            Text(
                "Привязать карты заново",
                payload={"cmd": "admin_contour_cards_rebuild", "id": contour.id},
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
        keyboard.add(
            Text(
                "К Контуру",
                payload={"cmd": "character_contour_view", "id": contour.id},
            ),
            color=KeyboardButtonColor.SECONDARY,
        )
        return keyboard.get_json()
    if len(contour.components) < contour.card_capacity:
        keyboard.add(
            Text(
                "Добавить карту",
                payload={"cmd": "admin_contour_card_add", "id": contour.id},
            ),
            color=KeyboardButtonColor.POSITIVE,
        )
    keyboard.add(
        Text(
            "Заменить карту",
            payload={"cmd": "admin_contour_card_replace", "id": contour.id},
        ),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "Убрать карту",
            payload={"cmd": "admin_contour_card_remove", "id": contour.id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "К Контуру",
            payload={"cmd": "character_contour_view", "id": contour.id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def contour_current_component_menu(contour: Contour, action: str) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for component in contour.components:
        keyboard.add(
            Text(
                _short_label(component.ownership.display_name),
                payload={"cmd": action, "component_id": component.id},
            ),
            color=(
                KeyboardButtonColor.NEGATIVE
                if action == "admin_contour_card_remove_confirm"
                else KeyboardButtonColor.PRIMARY
            ),
        )
        keyboard.row()
    keyboard.add(
        Text(
            "Назад",
            payload={"cmd": "admin_contour_components", "id": contour.id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def contour_available_cards_menu(
    cards: list[tuple[int, str, int]],
    *,
    command: str,
    target_id: int,
    page: int,
    pages: int,
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for ownership_id, name, free_count in cards:
        keyboard.add(
            Text(
                _short_label(f"{name} · свободно {free_count}"),
                payload={"cmd": command, "ownership_id": ownership_id},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
    _add_pager(keyboard, f"{command}_page", page, pages)
    keyboard.row()
    keyboard.add(
        Text(
            "Назад",
            payload={"cmd": "admin_contour_components", "id": target_id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def contour_ai_collect_menu() -> str:
    return ai_collect_menu("admin_contour_ai")


def contour_ai_confirm_menu() -> str:
    return ai_confirm_menu("admin_contour_ai")


def contour_delete_confirm_menu(contour_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "Да, разобрать",
            payload={"cmd": "admin_contour_delete_confirm", "id": contour_id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "Отмена",
            payload={"cmd": "character_contour_view", "id": contour_id},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def _add_pager(
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


def admin_character_cards_menu(character_id: int) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    keyboard.add(
        Text(
            "Выдать Особую",
            payload={"cmd": "admin_character_special_grant", "id": character_id},
        ),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text(
            "Забрать Особую",
            payload={"cmd": "admin_character_special_revoke", "id": character_id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "Выдать Закл./Конт.",
            payload={"cmd": "admin_character_registry_grant", "id": character_id},
        ),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text(
            "Забрать Закл./Конт.",
            payload={"cmd": "admin_character_registry_revoke", "id": character_id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "Добавить Обычную",
            payload={"cmd": "admin_character_ordinary_add", "id": character_id},
        ),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text(
            "Забрать Обычную",
            payload={"cmd": "admin_character_ordinary_revoke", "id": character_id},
        ),
        color=KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text(
            "Экспорт карт XLSX",
            payload={"cmd": "character_cards_export", "id": character_id},
        ),
        color=KeyboardButtonColor.PRIMARY,
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
