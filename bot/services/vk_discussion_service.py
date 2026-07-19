from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

import httpx

from bot.config import get_settings
from bot.services.errors import NotFoundError, ServiceError, ValidationError

_TOPIC_RE = re.compile(r"topic-(\d+)_(\d+)", re.IGNORECASE)
_API_URL = "https://api.vk.com/method/board.getComments"
_API_VERSION = "5.199"


@dataclass(frozen=True)
class DiscussionPhoto:
    url: str
    attachment: str
    width: int
    height: int


@dataclass(frozen=True)
class DiscussionApplication:
    group_id: int
    topic_id: int
    comment_id: int
    author_vk_id: int
    author_name: str
    author_screen_name: str
    text: str
    created_at: int
    photos: tuple[DiscussionPhoto, ...]
    content_hash: str

    @property
    def author_url(self) -> str:
        return f"https://vk.ru/id{self.author_vk_id}"

    @property
    def source_url(self) -> str:
        return (
            f"https://vk.ru/topic-{self.group_id}_{self.topic_id}"
            f"?post={self.comment_id}"
        )


def configured_topic() -> tuple[int, int]:
    settings = get_settings()
    if not settings.vk_board_token:
        raise ValidationError(
            "Чтение обсуждений не настроено. Добавьте VK_BOARD_TOKEN в .env."
        )
    if not settings.vk_applications_topic_url:
        raise ValidationError(
            "Добавьте VK_APPLICATIONS_TOPIC_URL в .env."
        )
    return parse_topic_url(settings.vk_applications_topic_url)


def parse_topic_url(value: str) -> tuple[int, int]:
    match = _TOPIC_RE.search(value.strip())
    if match is None:
        raise ValidationError(
            "Ссылка на обсуждение должна иметь вид "
            "https://vk.ru/topic-123_456."
        )
    return int(match.group(1)), int(match.group(2))


async def list_applications(
    *, offset: int = 0, count: int = 20
) -> tuple[int, list[DiscussionApplication]]:
    group_id, topic_id = configured_topic()
    if offset < 0:
        raise ValidationError("Смещение обсуждения не может быть отрицательным.")
    if not 1 <= count <= 100:
        raise ValidationError("За один запрос можно получить от 1 до 100 анкет.")
    payload = await _request(
        {
            "group_id": group_id,
            "topic_id": topic_id,
            "offset": offset,
            "count": count,
            "extended": 1,
            "sort": "asc",
        }
    )
    response = payload["response"]
    return int(response.get("count", 0)), _applications(response, group_id, topic_id)


async def get_application(comment_id: int) -> DiscussionApplication:
    if comment_id <= 0:
        raise ValidationError("ID комментария должен быть больше нуля.")
    group_id, topic_id = configured_topic()
    payload = await _request(
        {
            "group_id": group_id,
            "topic_id": topic_id,
            "start_comment_id": comment_id,
            "count": 1,
            "extended": 1,
            "sort": "asc",
        }
    )
    applications = _applications(payload["response"], group_id, topic_id)
    application = next(
        (item for item in applications if item.comment_id == comment_id), None
    )
    if application is None:
        raise NotFoundError(f"Комментарий обсуждения #{comment_id} не найден.")
    return application


async def _request(params: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    request_data = {
        **params,
        "access_token": settings.vk_board_token,
        "v": _API_VERSION,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(_API_URL, data=request_data)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ServiceError(f"Не удалось прочитать обсуждение VK: {error}") from error
    if "error" in payload:
        error = payload["error"]
        code = error.get("error_code", "?")
        message = error.get("error_msg", "неизвестная ошибка")
        raise ServiceError(f"VK API отклонил чтение обсуждения ({code}): {message}")
    if not isinstance(payload.get("response"), dict):
        raise ServiceError("VK API вернул некорректный ответ обсуждения.")
    return payload


def _applications(
    response: dict[str, object], group_id: int, topic_id: int
) -> list[DiscussionApplication]:
    profiles = {
        int(profile["id"]): profile
        for profile in response.get("profiles", [])
        if isinstance(profile, dict) and profile.get("id")
    }
    result: list[DiscussionApplication] = []
    for item in response.get("items", []):
        if not isinstance(item, dict):
            continue
        author_vk_id = int(item.get("from_id", 0))
        if author_vk_id <= 0:
            continue
        profile = profiles.get(author_vk_id, {})
        photos = tuple(_photos(item.get("attachments", [])))
        text = str(item.get("text", "")).strip()
        comment_id = int(item.get("id", 0))
        result.append(
            DiscussionApplication(
                group_id=group_id,
                topic_id=topic_id,
                comment_id=comment_id,
                author_vk_id=author_vk_id,
                author_name=(
                    f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
                ).strip(),
                author_screen_name=str(profile.get("screen_name", "")),
                text=text,
                created_at=int(item.get("date", 0)),
                photos=photos,
                content_hash=_content_hash(text, photos),
            )
        )
    return result


def _photos(attachments: object) -> list[DiscussionPhoto]:
    result: list[DiscussionPhoto] = []
    for attachment in attachments if isinstance(attachments, list) else []:
        if not isinstance(attachment, dict) or attachment.get("type") != "photo":
            continue
        photo = attachment.get("photo")
        if not isinstance(photo, dict):
            continue
        sizes = [
            size
            for size in photo.get("sizes", [])
            if isinstance(size, dict) and size.get("url")
        ]
        if not sizes:
            continue
        largest = max(
            sizes,
            key=lambda size: int(size.get("width", 0)) * int(size.get("height", 0)),
        )
        owner_id = int(photo.get("owner_id", 0))
        photo_id = int(photo.get("id", 0))
        access_key = str(photo.get("access_key", ""))
        suffix = f"_{access_key}" if access_key else ""
        result.append(
            DiscussionPhoto(
                url=str(largest["url"]),
                attachment=f"photo{owner_id}_{photo_id}{suffix}",
                width=int(largest.get("width", 0)),
                height=int(largest.get("height", 0)),
            )
        )
    return result


def _content_hash(text: str, photos: tuple[DiscussionPhoto, ...]) -> str:
    source = json.dumps(
        {"text": text, "photos": [photo.attachment for photo in photos]},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
