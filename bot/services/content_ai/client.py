import json

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ValidationError as PydanticValidationError

from bot.config import get_settings
from bot.services.errors import ServiceError, ValidationError


async def generate_structured(
    schema_name: str,
    model_type: type[BaseModel],
    system: str,
    user: str,
    image_urls: list[str] | None = None,
) -> dict[str, object]:
    settings = get_settings()
    if not settings.dslab_api_key:
        raise ValidationError(
            "DS Lab не настроен. Добавьте DSLAB_API_KEY в .env и перезапустите бота."
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
            api_key=settings.dslab_api_key,
            base_url=settings.dslab_base_url,
        ) as client:
            response = await client.chat.completions.create(
                model=(
                    settings.dslab_vision_model
                    if image_urls
                    else settings.dslab_model
                ),
                max_tokens=settings.dslab_max_tokens,
                temperature=0,
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
        raise ServiceError(f"Ошибка DS Lab: {error}") from error

    content = response.choices[0].message.content
    if not content:
        raise ServiceError("DS Lab вернул пустой ответ.")
    try:
        data = json.loads(content)
        return model_type.model_validate(data).model_dump()
    except (json.JSONDecodeError, PydanticValidationError) as error:
        raise ServiceError("Модель вернула ответ, который не прошёл проверку схемы.") from error
