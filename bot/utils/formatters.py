import re
from collections import defaultdict

from bot.database.models import (
    Card,
    CardOwnership,
    CardType,
    Character,
    CharacterTrophy,
    Contour,
    ShakeiTransaction,
)
from bot.services.character_service import STAT_FIELDS


def vk_plain_text(text: str) -> str:
    """Преобразует типичную Markdown-разметку модели в читаемый текст VK."""
    result = text.replace("\r\n", "\n").replace("\r", "\n")
    result = re.sub(r"(?m)^\s*```[^\n]*\n?", "", result)
    result = re.sub(r"\[([^\]]+)]\((https?://[^)]+)\)", r"\1 — \2", result)
    result = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", result)
    result = re.sub(r"(?m)^\s*[-+*]\s+", "• ", result)
    result = re.sub(r"(?m)^\s*>\s?", "› ", result)
    result = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", result)
    result = re.sub(r"__([^_\n]+)__", r"\1", result)
    result = re.sub(r"~~([^~\n]+)~~", r"\1", result)
    result = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", result)
    result = result.replace("```", "").replace("`", "")
    return result.strip()


def format_limit(card: Card, live_copies: int | None = None) -> str:
    if card.transform_limit is None:
        return "без лимита"
    copies = card.copies_count if live_copies is None else live_copies
    return f"{copies}/{card.transform_limit} (осталось {max(card.transform_limit - copies, 0)})"


def card_short(card: Card) -> str:
    """Краткая карточка для чата: ?карта."""
    slot = _card_game_number(card)
    lines = [
        f"🃏 {slot}{card.name} [{card.rarity.value}]",
        f"Публичный ID карты: {card_public_id(card)}",
        f"Внутренний ID БД: #{card.id}",
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
    slot = _card_game_number(card)
    lines = [
        f"🃏 {slot}{card.name} [{card.rarity.value}]",
        f"Публичный ID карты: {card_public_id(card)}",
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
    lines.append(f"\nВнутренний ID БД: #{card.id}")
    return "\n".join(lines)


def card_list(cards: list[Card]) -> str:
    if not cards:
        return "Ничего не найдено."
    return "\n".join(
        f"{_card_game_number(card)}"
        f"{card.name} [{card.rarity.value}] - {card.kind}"
        for card in cards
    )


def character_profile(
    character: Character,
    cards: list[Card] | None = None,
    _private_contours: list[Contour] | None = None,
    trophies: list[CharacterTrophy] | None = None,
    book_slots: object | None = None,
) -> str:
    """Публичная часть анкеты; Контуры намеренно никогда не форматируются здесь."""
    header = "❖ Основное"
    if not character.is_approved:
        header += "\n(анкета не подтверждена)"

    lines = [
        header,
        f"ID анкеты в БД: #{character.id}",
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
            lines.append(
                "Карты: "
                + ", ".join(f"{card_public_id(card)} · {card.name}" for card in cards)
            )
        else:
            lines.append("Карты: нет")

    if book_slots is not None:
        lines.extend(
            (
                f"Особые слоты: {book_slots.special_used}/{book_slots.special_limit}",
                f"Свободные слоты: {book_slots.free_used}/{book_slots.free_limit}",
            )
        )

    if trophies is not None:
        lines.append("\n🏆 Трофеи")
        lines.append(format_trophies(trophies, compact=True))

    if character.additional:
        lines.append(f"\n❦ Дополнительно\n{_truncate(character.additional, 900)}")

    return "\n".join(lines)


def format_contour(contour: Contour) -> str:
    components = list(contour.components)
    lines = [
        f"⌬ Слот {contour.slot}: {contour.name}",
        f"ID Контура: #{contour.id}",
        f"Карты: {len(components)}/{contour.card_capacity}",
    ]
    if components:
        lines.append(
            "Состав: "
            + " + ".join(
                _ownership_label(component.ownership)
                for component in components
            )
        )
    elif contour.composition:
        lines.extend(
            (
                f"Старый состав: {contour.composition}",
                "⚠ Карты ещё не привязаны к физическим копиям. Администратору "
                "нужно пересобрать состав.",
            )
        )
    fields = (
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


def character_card_holdings(
    ownerships: list[CardOwnership], book_slots: object | None = None
) -> str:
    slot_header = ""
    if book_slots is not None:
        slot_header = (
            f"Особые слоты: {book_slots.special_used}/{book_slots.special_limit}\n"
            f"Свободные слоты: {book_slots.free_used}/{book_slots.free_limit} "
            f"(осталось {book_slots.free_remaining})\n\n"
        )
    if not ownerships:
        return slot_header + "Карт пока нет."
    grouped: dict[tuple[CardType, int | str], list[CardOwnership]] = defaultdict(list)
    for ownership in ownerships:
        key: int | str = (
            ownership.card_id
            if ownership.card_id is not None
            else ownership.display_name.casefold()
        )
        grouped[(ownership.display_type, key)].append(ownership)
    sections: list[str] = []
    for card_type, title in (
        (CardType.SPECIAL, "Карты Особых слотов"),
        (CardType.SPELL, "Карты Заклинаний"),
        (CardType.CONTOUR, "Контурные карты"),
        (CardType.ORDINARY, "Обычные карты"),
        (CardType.GM, "Карты ГеймМастеров"),
    ):
        lines: list[str] = []
        for (group_type, _), items in grouped.items():
            if group_type is not card_type:
                continue
            ownership = items[0]
            bound = sum(item.contour_component is not None for item in items)
            label = _ownership_label(ownership)
            lines.append(
                f"{label} [{ownership.display_rarity.value}] — всего {len(items)}, "
                f"свободно {len(items) - bound}, связано {bound}"
            )
        sections.append(f"{title}:\n" + ("\n".join(lines) if lines else "—"))
    return slot_header + "\n\n".join(sections)


def card_owner_holdings(ownerships: list[CardOwnership]) -> str:
    if not ownerships:
        return "Этой карты пока ни у кого нет."
    grouped: dict[int, list[CardOwnership]] = defaultdict(list)
    for ownership in ownerships:
        grouped[ownership.character_id].append(ownership)
    lines = []
    for items in grouped.values():
        character = items[0].character
        bound = sum(item.contour_component is not None for item in items)
        lines.append(
            f"#{character.id} · {character.name} — всего {len(items)}, "
            f"свободно {len(items) - bound}, связано {bound}"
        )
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


def format_trophies(
    trophies: list[CharacterTrophy], *, compact: bool = False
) -> str:
    if not trophies:
        return "Трофеев пока нет."
    icons = {"BRONZE": "🥉", "SILVER": "🥈", "GOLD": "🥇"}
    if compact:
        return "\n".join(
            f"{icons[trophy.rank.name]} {trophy.name} — {trophy.rank.value}"
            for trophy in trophies
        )
    blocks = []
    for trophy in trophies:
        lines = [
            f"{icons[trophy.rank.name]} {trophy.name}",
            f"Ранг: {trophy.rank.value}",
            f"ID трофея: #{trophy.id}",
        ]
        if trophy.description:
            lines.append(f"Описание: {trophy.description}")
        if trophy.reward:
            lines.append(f"Награда: {trophy.reward}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _card_game_number(card: Card) -> str:
    if card.card_type is CardType.SPECIAL and card.number is not None:
        return f"Особый слот №{card.number} · "
    if card.registry_number is not None:
        return f"ID #{card.registry_number} · "
    return ""


def card_public_id(card: Card) -> str:
    if card.card_type is CardType.SPECIAL and card.number is not None:
        return f"#{card.number}"
    if card.registry_number is not None:
        return f"#{card.registry_number}"
    return "без публичного ID"


def _ownership_label(ownership: CardOwnership) -> str:
    if ownership.card is None:
        return ownership.display_name
    return f"{_card_game_number(ownership.card)}{ownership.card.name}"
