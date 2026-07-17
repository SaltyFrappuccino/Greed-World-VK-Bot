from bot.database.models import Card, CardType, Character, Contour, ShakeiTransaction
from bot.services.character_service import STAT_FIELDS


def format_limit(card: Card, live_copies: int | None = None) -> str:
    if card.transform_limit is None:
        return "без лимита"
    copies = card.copies_count if live_copies is None else live_copies
    return f"{copies}/{card.transform_limit} (осталось {max(card.transform_limit - copies, 0)})"


def card_short(card: Card) -> str:
    """Краткая карточка для чата: ?!карта."""
    slot = f"№{card.number} " if card.number is not None else ""
    lines = [
        f"🃏 {slot}{card.name} [{card.rarity.value}]",
        f"Тип: {card.card_type.value}",
        f"Преобразования: {format_limit(card)}",
    ]
    if card.kind.casefold() != card.card_type.value.casefold():
        label = "Подтип контура" if card.card_type is CardType.CONTOUR else "Содержимое"
        lines.insert(2, f"{label}: {card.kind}")
    if card.description:
        lines.append(f"\n{_truncate(card.description, 400)}")
    return "\n".join(lines)


def card_full(card: Card, live_copies: int | None = None) -> str:
    """Полная карточка для ЛС и админки."""
    slot = f"№{card.number} " if card.number is not None else ""
    lines = [
        f"🃏 {slot}{card.name} [{card.rarity.value}]",
        f"Тип: {card.card_type.value}",
        f"Преобразования: {format_limit(card, live_copies)}",
    ]
    if card.kind.casefold() != card.card_type.value.casefold():
        label = "Подтип контура" if card.card_type is CardType.CONTOUR else "Содержимое"
        lines.insert(2, f"{label}: {card.kind}")
    if card.description:
        lines.append(f"\nОписание:\n{card.description}")
    if card.usage:
        lines.append(f"\nСпособ использования:\n{card.usage}")
    lines.append(f"\nID в реестре: {card.id}")
    return "\n".join(lines)


def card_list(cards: list[Card]) -> str:
    if not cards:
        return "Ничего не найдено."
    return "\n".join(
        f"{'№' + str(card.number) + ' ' if card.number is not None else ''}"
        f"{card.name} [{card.rarity.value}] - {card.kind}"
        for card in cards
    )


def character_profile(
    character: Character,
    cards: list[Card] | None = None,
    contours: list[Contour] | None = None,
) -> str:
    """Анкета персонажа."""
    header = "❖ Основное"
    if not character.is_approved:
        header += "\n(анкета не подтверждена)"

    lines = [
        header,
        f"\n➤ Имя персонажа\n{character.name}",
        f"\n➤ Возраст\n{character.age if character.age is not None else '—'}",
        f"\n➤ Пол\n{character.gender or '—'}",
        f"\n➤ Внешность\n{_truncate(character.appearance, 900) or '—'}",
        f"\n✎ Характер\n{_truncate(character.personality, 900) or '—'}",
        f"\n☙ Биография\n{_truncate(character.biography, 1200) or '—'}",
        "\n⚖ Статы",
    ]
    for field, title in STAT_FIELDS.items():
        lines.append(f"➤ {title.capitalize()}　{getattr(character, field)}")

    lines.extend(
        (
            f"\n⚔ Навыки\n{_truncate(character.skills, 700) or '—'}",
            f"\n♛ Общий рейтинг\n{character.overall_rating.value}",
            f"\n⌾ Шакеи\n{character.shakei_balance}",
        )
    )

    if cards is not None:
        lines.append("")
        if cards:
            lines.append("Карты: " + ", ".join(card.name for card in cards))
        else:
            lines.append("Карты: нет")

    if contours is not None:
        lines.append("\n⌬ Контуры")
        if contours:
            for contour in contours:
                lines.append(format_contour(contour))
        else:
            lines.append("Оба слота пусты.")

    if character.additional:
        lines.append(f"\n❦ Дополнительно\n{_truncate(character.additional, 900)}")

    return "\n".join(lines)


def format_contour(contour: Contour) -> str:
    lines = [f"\n⌬ Слот {contour.slot}: {contour.name}"]
    fields = (
        ("Состав", contour.composition),
        ("Внешний вид", contour.appearance),
        ("Основной эффект", contour.primary_effect),
        ("Дополнительные возможности", contour.additional_capabilities),
        ("Условия активации", contour.activation_conditions),
        ("Продолжительность", contour.duration),
        ("Проводимость", contour.conductivity),
        ("Влияние на Перегрузку", contour.overload_impact),
    )
    lines.extend(f"{title}: {_truncate(value, 500)}" for title, value in fields if value)
    return "\n".join(lines)


def transaction_line(transaction: ShakeiTransaction, character_id: int) -> str:
    """Одна строка истории: знак считается относительно указанного персонажа."""
    if transaction.to_character_id == character_id:
        sign = "+"
    else:
        sign = "−"

    date = transaction.created_at.strftime("%d.%m.%Y") if transaction.created_at else ""
    reason = f" - {transaction.reason}" if transaction.reason else ""
    return f"{date} {sign}{transaction.amount}{reason}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
