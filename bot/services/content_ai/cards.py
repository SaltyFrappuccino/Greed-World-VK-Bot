from bot.database.models import CardType
from bot.services.card_template_service import CONTOUR_SUBTYPES
from bot.services.content_ai.client import generate_structured
from bot.services.content_ai.contracts import CardDraft
from bot.services.errors import ValidationError


async def generate_card(source: str, card_type: CardType) -> CardDraft:
    subtype_context = ""
    if card_type is CardType.CONTOUR:
        subtype_context = (
            "Для kind выбери ровно одно значение из списка: "
            + "; ".join(CONTOUR_SUBTYPES)
            + "."
        )
    elif card_type is CardType.SPELL:
        subtype_context = (
            "Для kind верни «Заклинание». В usage отдельно и ясно укажи команду "
            "активации, дополнительную команду/цель, если она есть, и расходование карты."
        )
    elif card_type is CardType.ORDINARY:
        subtype_context = (
            "Для kind укажи простой вид содержимого: предмет, оружие, еда, инструмент, "
            "животное или другое точное существительное."
        )
    elif card_type is CardType.SPECIAL:
        subtype_context = "Для kind кратко назови, что содержится в Особой карте."
    else:
        subtype_context = "Для kind верни «ГеймМастерская»."

    system = f"""Ты оформляешь карту для текстовой ролевой «Жадный Мир».
Тип карты уже выбран администратором: {card_type.value}. Не меняй его.

Контекст системы:
- Карта хранит название, вид, описание, способ использования, ограничения и редкость H–SS.
- Редкость показывает ценность и распространённость, а не автоматически силу. Если данных мало, выбирай консервативную H.
- Особые карты занимают слот 0–99 и могут иметь лимит преобразований. Номер и лимит администратор задаёт отдельно — не включай их в поля.
- Заклинание является готовым эффектом. Обычно активируется произнесением названия, иногда требует цели или второй команды; расходование должно быть явно описано.
- Обычная карта содержит предмет, оружие, еду, инструмент, животное или другое обычное содержимое. Она может быть сильной, но не требует реестра.
- Контурная карта задаёт форму или поведение способности и редко полезна сама по себе. Формы: Покров, Оружие, Снаряд, Область, Ловушка, Барьер. Эффекты: Существо, Метка, Превращение, Связь.
- Карты ГеймМастеров недоступны игрокам и служат ведущим.

{subtype_context}

Преобразуй пользовательскую идею в ясную карточку. Сохрани все явно заданные факты и ограничения. Не добавляй сюжетных владельцев, историю получения, номер слота, лимит преобразований или скрытые свойства. Не обещай автоматическую победу. Если пользователь не описал активацию или расходование, честно оставь соответствующую часть usage пустой, не придумывай ритуал.
Верни только объект заданной JSON-схемы."""
    user = f"""Оформи идею из блока SOURCE как карту типа «{card_type.value}».

<SOURCE>
{source}
</SOURCE>"""
    data = await generate_structured("card_draft", CardDraft, system, user)
    draft = CardDraft.model_validate(data)
    if not draft.name.strip():
        raise ValidationError("AI не смог определить название карты.")
    if card_type is CardType.CONTOUR and draft.kind not in CONTOUR_SUBTYPES:
        raise ValidationError(
            "AI вернул неизвестный подтип Контурной карты. Попробуйте уточнить форму или эффект."
        )
    return draft


