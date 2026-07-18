import logging

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError as PydanticValidationError

from bot.config import get_settings
from bot.services.admin_ai.contracts import AdminAssistantTurn, parse_turn
from bot.services.admin_ai.prompt import build_system_prompt
from bot.services.errors import ServiceError, ValidationError

logger = logging.getLogger(__name__)
AGENT_MAX_TOKENS = 3_500
REPAIR_MAX_TOKENS = 1_500


async def generate_admin_assistant_turn(
    history: list[dict[str, str]], *, image_urls: list[str] | None = None
) -> AdminAssistantTurn:
    settings = get_settings()
    if not settings.dslab_api_key:
        raise ValidationError(
            "DS Lab не настроен. Добавьте DSLAB_API_KEY в .env и перезапустите бота."
        )
    messages: list[dict[str, object]] = [
        {"role": "system", "content": build_system_prompt()},
        *history,
    ]
    if image_urls:
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Изображения относятся к последней просьбе."},
                    *(
                        {"type": "image_url", "image_url": {"url": url}}
                        for url in image_urls
                    ),
                ],
            }
        )
    try:
        async with AsyncOpenAI(
            api_key=settings.dslab_api_key, base_url=settings.dslab_base_url
        ) as client:
            response = await client.chat.completions.create(
                model=settings.dslab_vision_model if image_urls else settings.dslab_model,
                max_tokens=min(settings.dslab_max_tokens, AGENT_MAX_TOKENS),
                temperature=0,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            try:
                return parse_turn(content)
            except (ValueError, PydanticValidationError) as error:
                logger.warning(
                    "Некорректный JSON AI-Ассистента: %s; ответ=%r",
                    error,
                    content[:2000],
                )
                return await _repair_turn(client, settings.dslab_model, content, error)
    except OpenAIError as error:
        raise ServiceError(f"Ошибка DS Lab: {error}") from error


async def _repair_turn(
    client: AsyncOpenAI, model: str, content: str, error: Exception
) -> AdminAssistantTurn:
    response = await client.chat.completions.create(
        model=model,
        max_tokens=REPAIR_MAX_TOKENS,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты исправляешь структуру ответа. Верни только JSON с полями "
                    "kind, message, tools, actions, warnings. Не меняй намерение и "
                    "не добавляй новых действий. Допустимые kind: answer, "
                    "clarification, read_tools, action_plan."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Ошибка проверки: {str(error)[:1500]}\n"
                    f"Некорректный ответ:\n{content[:6000]}"
                ),
            },
        ],
        response_format={"type": "json_object"},
    )
    repaired = response.choices[0].message.content or ""
    try:
        return parse_turn(repaired)
    except (ValueError, PydanticValidationError) as error:
        logger.warning("Repair JSON AI-Ассистента не удался: %s", error)
        raise ServiceError(
            "AI вернул повреждённый ответ даже после автоматического исправления. "
            "Попробуйте повторить задачу короче."
        ) from error
