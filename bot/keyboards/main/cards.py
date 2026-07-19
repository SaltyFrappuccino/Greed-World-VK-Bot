from vkbottle import Keyboard, KeyboardButtonColor, Text

from bot.database.models import Card, CardType
from bot.keyboards.main.shared import _add_page_navigation, _short_label


def card_registry_menu(
    cards: list[Card],
    page: int,
    pages: int,
    *,
    card_type: CardType = CardType.SPECIAL,
    is_admin: bool = False,
) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for index, card in enumerate(cards):
        if index and index % 2 == 0:
            keyboard.row()
        keyboard.add(
            Text(
                _short_label(card.name),
                payload={
                    "cmd": "card_registry_view",
                    "id": card.id,
                    "page": page,
                    "type": card_type.name,
                },
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
    if cards:
        keyboard.row()
    _add_page_navigation(
        keyboard, "cards_page", page, pages, extra={"type": card_type.name}
    )
    keyboard.row()
    keyboard.add(
        Text(
            "Поиск карты",
            payload={
                "cmd": "card_search",
                "page": page,
                "type": card_type.name,
            },
        )
    )
    keyboard.add(
        Text(
            "К категориям карт",
            payload={"cmd": "cards"},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()


def card_registry_detail_menu(
    card_id: int,
    page: int,
    *,
    card_type: CardType = CardType.SPECIAL,
    is_admin: bool,
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
        Text(
            "К реестру карт",
            payload={"cmd": "cards_page", "page": page, "type": card_type.name},
        ),
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


def card_registry_categories(*, is_admin: bool) -> str:
    keyboard = Keyboard(one_time=False, inline=False)
    for card_type, title in (
        (CardType.SPECIAL, "Особые слоты"),
        (CardType.SPELL, "Заклинания"),
        (CardType.CONTOUR, "Контурные"),
    ):
        keyboard.add(
            Text(
                title,
                payload={"cmd": "cards_page", "page": 0, "type": card_type.name},
            ),
            color=KeyboardButtonColor.PRIMARY,
        )
        keyboard.row()
    if is_admin:
        keyboard.add(
            Text("Экспорт реестра XLSX", payload={"cmd": "admin_cards_export"}),
            color=KeyboardButtonColor.POSITIVE,
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


