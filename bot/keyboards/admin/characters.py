from vkbottle import Keyboard, KeyboardButtonColor, Text


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
            "Выдать реестровую",
            payload={"cmd": "admin_character_registry_grant", "id": character_id},
        ),
        color=KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text(
            "Забрать реестровую",
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
    keyboard.add(
        Text(
            "Экспорт анкеты XLSX",
            payload={"cmd": "character_profile_export", "id": character_id},
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
