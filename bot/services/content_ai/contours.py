from bot.services.content_ai.client import generate_structured
from bot.services.content_ai.contracts import ContourDraft


async def generate_contour(
    source: str,
    character_context: str,
    card_context: str,
    image_urls: list[str] | None = None,
) -> ContourDraft:
    system = """Ты редактор Контуров текстовой ролевой «Жадный Мир».
Контур — собранная из 2–5 карт способность. Состав уже выбран администратором и передан отдельным блоком.
Запрещено добавлять, заменять, удалять или переименовывать карты состава. Не выводи состав в JSON — заполняй только описание готовой способности.
Не обещай автоматическую победу и обязательно сформулируй ограничения, условия активации,
продолжительность, проводимость и влияние на Перегрузку.
Если приложено изображение, используй его только для поля внешнего вида Контура;
не выводи из изображения состав, эффекты или игровые свойства."""
    user = (
        f"Контекст персонажа:\n{character_context}\n\n"
        f"Зафиксированный состав:\n{card_context}\n\nИдея Контура:\n{source}"
    )
    data = await generate_structured(
        "contour", ContourDraft, system, user, image_urls=image_urls
    )
    return ContourDraft.model_validate(data)



def contour_fields(draft: ContourDraft) -> dict[str, object]:
    return draft.model_dump()


