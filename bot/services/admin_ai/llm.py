import asyncio
import logging
from time import perf_counter

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, OpenAIError
from pydantic import ValidationError as PydanticValidationError

from bot.config import get_settings
from bot.services.admin_ai.contracts import AdminAssistantTurn, parse_turn
from bot.services.admin_ai.diagnostics import elapsed_ms, response_shape
from bot.services.admin_ai.prompt import build_system_prompt
from bot.services.errors import ServiceError, ValidationError

logger = logging.getLogger("zhadny_mir.ai_agent.llm")
REPAIR_MAX_TOKENS = 1_500
RETRY_BASE_DELAY_SECONDS = 0.5


async def generate_admin_assistant_turn(
    history: list[dict[str, str]],
    *,
    image_urls: list[str] | None = None,
    request_id: str = "standalone",
    round_number: int = 0,
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
    model = settings.dslab_vision_model if image_urls else settings.dslab_model
    started_at = perf_counter()
    logger.info(
        "request.start request_id=%s round=%s model=%s timeout_seconds=%s "
        "max_tokens=%s max_retries=%s messages=%s history_chars=%s images=%s",
        request_id,
        round_number,
        model,
        settings.dslab_agent_timeout_seconds,
        settings.dslab_agent_max_tokens,
        settings.dslab_agent_max_retries,
        len(messages),
        sum(len(str(item.get("content", ""))) for item in history),
        len(image_urls or []),
    )
    try:
        async with AsyncOpenAI(
            api_key=settings.dslab_api_key,
            base_url=settings.dslab_base_url,
            timeout=settings.dslab_agent_timeout_seconds,
            max_retries=0,
        ) as client:
            async with asyncio.timeout(settings.dslab_agent_timeout_seconds):
                response = await _completion_with_retries(
                    client,
                    max_retries=settings.dslab_agent_max_retries,
                    request_id=request_id,
                    round_number=round_number,
                    model=model,
                    max_tokens=settings.dslab_agent_max_tokens,
                    temperature=0,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                choice = response.choices[0]
                logger.info(
                    "request.done request_id=%s round=%s duration_ms=%s response_id=%s "
                    "finish_reason=%s response_chars=%s prompt_tokens=%s completion_tokens=%s",
                    request_id,
                    round_number,
                    elapsed_ms(started_at),
                    getattr(response, "id", None),
                    getattr(choice, "finish_reason", None),
                    len(content),
                    getattr(usage, "prompt_tokens", None),
                    getattr(usage, "completion_tokens", None),
                )
                try:
                    turn = parse_turn(content)
                    logger.info(
                        "parse.ok request_id=%s round=%s kind=%s tools=%s actions=%s warnings=%s",
                        request_id,
                        round_number,
                        turn.kind,
                        len(turn.tools),
                        len(turn.actions),
                        len(turn.warnings),
                    )
                    return turn
                except (ValueError, PydanticValidationError) as error:
                    logger.warning(
                        "parse.failed request_id=%s round=%s error_type=%s error=%s %s",
                        request_id,
                        round_number,
                        type(error).__name__,
                        error,
                        response_shape(content),
                    )
                    logger.debug(
                        "parse.failed.raw request_id=%s round=%s content=%r",
                        request_id,
                        round_number,
                        content[:6000],
                    )
                    return await _repair_turn(
                        client,
                        settings.dslab_model,
                        content,
                        error,
                        max_retries=settings.dslab_agent_max_retries,
                        request_id=request_id,
                        round_number=round_number,
                    )
    except (APITimeoutError, TimeoutError) as error:
        logger.error(
            "request.timeout request_id=%s round=%s duration_ms=%s model=%s "
            "timeout_seconds=%s",
            request_id,
            round_number,
            elapsed_ms(started_at),
            model,
            settings.dslab_agent_timeout_seconds,
            exc_info=True,
        )
        raise ServiceError(
            f"DS Lab не ответил за {settings.dslab_agent_timeout_seconds:g} секунд. "
            f"Код запроса: {request_id}."
        ) from error
    except APIConnectionError as error:
        attempts = settings.dslab_agent_max_retries + 1
        logger.error(
            "request.connection_failed request_id=%s round=%s duration_ms=%s "
            "model=%s attempts=%s error=%s",
            request_id,
            round_number,
            elapsed_ms(started_at),
            model,
            attempts,
            error,
            exc_info=True,
        )
        raise ServiceError(
            f"Не удалось соединиться с DS Lab после {attempts} попыток. "
            "Это временная сетевая ошибка; данные не изменены. "
            f"AI-режим остаётся активным. Код запроса: {request_id}."
        ) from error
    except OpenAIError as error:
        logger.error(
            "request.failed request_id=%s round=%s duration_ms=%s model=%s error=%s",
            request_id,
            round_number,
            elapsed_ms(started_at),
            model,
            error,
            exc_info=True,
        )
        raise ServiceError(f"Ошибка DS Lab: {error}. Код запроса: {request_id}.") from error


async def _repair_turn(
    client: AsyncOpenAI,
    model: str,
    content: str,
    error: Exception,
    *,
    max_retries: int,
    request_id: str,
    round_number: int,
) -> AdminAssistantTurn:
    started_at = perf_counter()
    logger.info(
        "repair.start request_id=%s round=%s model=%s source_chars=%s",
        request_id,
        round_number,
        model,
        len(content),
    )
    response = await _completion_with_retries(
        client,
        max_retries=max_retries,
        request_id=request_id,
        round_number=round_number,
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
    logger.info(
        "repair.done request_id=%s round=%s duration_ms=%s response_chars=%s",
        request_id,
        round_number,
        elapsed_ms(started_at),
        len(repaired),
    )
    try:
        turn = parse_turn(repaired)
        logger.info(
            "repair.parse.ok request_id=%s round=%s kind=%s tools=%s actions=%s",
            request_id,
            round_number,
            turn.kind,
            len(turn.tools),
            len(turn.actions),
        )
        return turn
    except (ValueError, PydanticValidationError) as error:
        logger.warning(
            "repair.parse.failed request_id=%s round=%s error_type=%s error=%s %s",
            request_id,
            round_number,
            type(error).__name__,
            error,
            response_shape(repaired),
        )
        logger.debug(
            "repair.parse.failed.raw request_id=%s round=%s content=%r",
            request_id,
            round_number,
            repaired[:6000],
        )
        raise ServiceError(
            "AI вернул повреждённый ответ даже после автоматического исправления. "
            f"Код запроса: {request_id}."
        ) from error


async def _completion_with_retries(
    client: AsyncOpenAI,
    *,
    max_retries: int,
    request_id: str,
    round_number: int,
    **request: object,
):
    """Повторить только временный сетевой сбой, не ошибки ответа модели."""
    attempts = max(0, max_retries) + 1
    for attempt in range(1, attempts + 1):
        try:
            return await client.chat.completions.create(**request)
        except (APIConnectionError, APITimeoutError) as error:
            if attempt >= attempts:
                raise
            delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "request.retry request_id=%s round=%s attempt=%s next_attempt=%s "
                "delay_seconds=%s error_type=%s error=%s",
                request_id,
                round_number,
                attempt,
                attempt + 1,
                delay,
                type(error).__name__,
                error,
            )
            await asyncio.sleep(delay)
    raise RuntimeError("Недостижимое состояние повторных запросов DS Lab")
