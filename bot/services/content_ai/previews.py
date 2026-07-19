from bot.database.models import CardType
from bot.services.content_ai.contracts import CardDraft, CharacterDraft, ContourDraft


def character_preview(draft: CharacterDraft) -> str:
    skills = "\n".join(f"➤ {skill}" for skill in draft.skills) or "—"
    return f"""Предпросмотр — в базу ещё ничего не записано.

❖ Основное

➤ Имя персонажа
{draft.name}

➤ Возраст
{draft.age if draft.age is not None else '—'}

➤ Пол
{draft.gender or '—'}

➤ Внешность
{draft.appearance or '—'}

✎ Характер
{draft.personality or '—'}

☙ Биография
{draft.biography or '—'}

⚖ Статы
➤ Стрессоустойчивость　{draft.stress_resistance if draft.stress_resistance is not None else '—'}
➤ Речевой Аппарат　{draft.speech if draft.speech is not None else '—'}
➤ Чуйка　{draft.intuition if draft.intuition is not None else '—'}
➤ Хребет　{draft.spine if draft.spine is not None else '—'}
➤ Воля　{draft.will if draft.will is not None else '—'}
➤ Нюх　{draft.scent if draft.scent is not None else '—'}

⚔ Навыки
{skills}

♛ Общий рейтинг
H

⌾ Шакеи
0

⌬ Контуры
Оба Контура пока пусты. Доступно 2 Контура на 2 карты каждый.

❦ Дополнительно
{draft.additional or '—'}"""


def contour_preview(draft: ContourDraft) -> str:
    return f"""Предпросмотр Контура

Название: {draft.name}
Внешний вид: {draft.appearance}
Основной эффект: {draft.primary_effect}
Дополнительные возможности: {draft.additional_capabilities}
Условия активации: {draft.activation_conditions}
Продолжительность: {draft.duration}
Проводимость: {draft.conductivity}
Влияние на Перегрузку: {draft.overload_impact}"""


def card_preview(draft: CardDraft, card_type: CardType) -> str:
    return f"""Предпросмотр карты — в базу ещё ничего не записано.

Тип: {card_type.value}
Название: {draft.name}
Вид: {draft.kind}
Редкость: {draft.rarity.value}

Описание:
{draft.description or '—'}

Способ использования:
{draft.usage or '—'}"""
