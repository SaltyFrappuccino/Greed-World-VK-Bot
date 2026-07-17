import json

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from bot.config import get_settings
from bot.services.errors import ServiceError, ValidationError


class CharacterDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Имя персонажа")
    age: int | None = Field(description="Возраст; null, если он принципиально неизвестен")
    gender: str = Field(description="Пол персонажа")
    appearance: str = Field(description="Внешность персонажа и его книги")
    personality: str = Field(description="Характер персонажа")
    biography: str = Field(description="Биография персонажа")
    stress_resistance: int | None = Field(ge=1, le=5)
    speech: int | None = Field(ge=1, le=5)
    intuition: int | None = Field(ge=1, le=5)
    spine: int | None = Field(ge=1, le=5)
    will: int | None = Field(ge=1, le=5)
    scent: int | None = Field(ge=1, le=5)
    skills: list[str] = Field(
        description="Короткие нарративные теги навыков без числовых значений"
    )
    additional: str = Field(description="Связи, привычки, страхи и прочие детали")


class ContourDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    composition: str = Field(
        description="Названия не более чем двух входящих в Контур карт"
    )
    appearance: str
    primary_effect: str
    additional_capabilities: str
    activation_conditions: str
    duration: str
    conductivity: str
    overload_impact: str


async def generate_character(
    source: str, image_urls: list[str] | None = None
) -> CharacterDraft:
    has_images = bool(image_urls)
    system = f"""Ты оператор переноса анкет текстовой ролевой «Жадный Мир», а не соавтор.
Разложи исходный материал по полям анкеты максимально дословно.
Запрещено добавлять факты, расширять текст, художественно переписывать, исправлять мотивацию,
придумывать внешность, книгу, характер, биографию, навыки или значения статов.
Если сведений для строкового поля нет, верни пустую строку; для возраста или стата — null;
для навыков — пустой список. Не пытайся сделать анкету полной.
Статы допустимы только от 1 до 5 и переносятся лишь тогда, когда их значения явно указаны.
Навыки переноси как короткие нарративные теги без цифр. Рейтинг, Шакеи, карты и Контуры не извлекай.
Изображения приложены: {'да' if has_images else 'нет'}.
Если изображений нет и внешность не описана в тексте, поле appearance обязано быть пустой строкой.
Если изображение есть, разрешено описать по нему только непосредственно видимые черты внешности,
одежду и книгу. Не определяй личность, характер, биографию, способности или скрытые свойства по изображению."""
    data = await _generate(
        "character_sheet", CharacterDraft, system, source, image_urls=image_urls
    )
    return CharacterDraft.model_validate(data)


async def generate_contour(
    source: str,
    character_context: str,
    image_urls: list[str] | None = None,
) -> ContourDraft:
    system = """Ты редактор Контуров текстовой ролевой «Жадный Мир».
Контур — собранная из карт способность. В одном Контуре не больше двух карт. Преврати идею в ясное, непротиворечивое описание.
Не выдумывай отсутствующие карты: если состав не дан, прямо укажи, что его нужно определить. Если названо больше двух карт, не выбирай за администратора и укажи, что состав нужно сократить.
Не обещай автоматическую победу и обязательно сформулируй ограничения, условия активации,
продолжительность, проводимость и влияние на Перегрузку.
Если приложено изображение, используй его только для поля внешнего вида Контура;
не выводи из изображения состав, эффекты или игровые свойства."""
    user = f"Контекст персонажа:\n{character_context}\n\nИдея Контура:\n{source}"
    data = await _generate(
        "contour", ContourDraft, system, user, image_urls=image_urls
    )
    return ContourDraft.model_validate(data)


async def _generate(
    schema_name: str,
    model_type: type[BaseModel],
    system: str,
    user: str,
    image_urls: list[str] | None = None,
) -> dict[str, object]:
    settings = get_settings()
    if not settings.aitunnel_api_key:
        raise ValidationError(
            "AI Tunnel не настроен. Добавьте AITUNNEL_API_KEY в .env и перезапустите бота."
        )
    if not user.strip() and not image_urls:
        raise ValidationError("Добавьте текст или изображение.")

    user_content: str | list[dict[str, object]] = user
    if image_urls:
        user_content = [
            {
                "type": "text",
                "text": user or "Текст отсутствует. Используй изображение только для поля внешности.",
            },
            *(
                {"type": "image_url", "image_url": {"url": image_url}}
                for image_url in image_urls
            ),
        ]

    try:
        async with AsyncOpenAI(
            api_key=settings.aitunnel_api_key,
            base_url=settings.aitunnel_base_url,
        ) as client:
            response = await client.chat.completions.create(
                model=settings.aitunnel_model,
                max_tokens=settings.aitunnel_max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": model_type.model_json_schema(),
                    },
                },
            )
    except OpenAIError as error:
        raise ServiceError(f"Ошибка AI Tunnel: {error}") from error

    content = response.choices[0].message.content
    if not content:
        raise ServiceError("AI Tunnel вернул пустой ответ.")
    try:
        data = json.loads(content)
        return model_type.model_validate(data).model_dump()
    except (json.JSONDecodeError, PydanticValidationError) as error:
        raise ServiceError("Модель вернула ответ, который не прошёл проверку схемы.") from error


def character_fields(draft: CharacterDraft) -> dict[str, object]:
    data = draft.model_dump()
    if not draft.name.strip():
        raise ValidationError("В исходнике не указано имя персонажа.")
    missing_stats = [
        title
        for field, title in (
            ("stress_resistance", "стрессоустойчивость"),
            ("speech", "речевой аппарат"),
            ("intuition", "чуйка"),
            ("spine", "хребет"),
            ("will", "воля"),
            ("scent", "нюх"),
        )
        if data[field] is None
    ]
    if missing_stats:
        raise ValidationError(
            "В исходнике не указаны статы: " + ", ".join(missing_stats) + "."
        )
    skills = data.pop("skills")
    data["skills"] = "\n".join(f"➤ {skill.strip()}" for skill in skills if skill.strip())
    data["is_approved"] = True
    return data


def contour_fields(draft: ContourDraft) -> dict[str, object]:
    return draft.model_dump()


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
Состав: {draft.composition}
Внешний вид: {draft.appearance}
Основной эффект: {draft.primary_effect}
Дополнительные возможности: {draft.additional_capabilities}
Условия активации: {draft.activation_conditions}
Продолжительность: {draft.duration}
Проводимость: {draft.conductivity}
Влияние на Перегрузку: {draft.overload_impact}"""
