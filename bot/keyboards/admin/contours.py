from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import CardType, Contour, Rarity
from bot.services.card_template_service import CONTOUR_SUBTYPES


from bot.keyboards.admin.shared import _add_pager, _short_label


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

