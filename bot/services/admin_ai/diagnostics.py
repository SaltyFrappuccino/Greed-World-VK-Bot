import hashlib
import json
from time import perf_counter
from uuid import uuid4


SENSITIVE_KEYS = {"api_key", "authorization", "password", "secret", "token"}


def new_request_id() -> str:
    return uuid4().hex[:12]


def elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)


def safe_json(value: object, *, limit: int = 1200) -> str:
    text = json.dumps(_redact(value), ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def result_summary(value: object) -> str:
    if isinstance(value, dict):
        return f"dict keys={sorted(map(str, value.keys()))[:20]}"
    if isinstance(value, list):
        return f"list count={len(value)}"
    if isinstance(value, str):
        return f"str chars={len(value)}"
    return type(value).__name__


def response_shape(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:12]
    base = f"chars={len(content)} sha256={digest}"
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        return f"{base} malformed_json_at={error.pos}"
    if not isinstance(value, dict):
        return f"{base} root={type(value).__name__}"
    shape = {key: _shape(item) for key, item in value.items()}
    return f"{base} shape={safe_json(shape, limit=800)}"


def _shape(value: object) -> str:
    if isinstance(value, list):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        return f"dict[{len(value)}]"
    if isinstance(value, str):
        return f"str[{len(value)}]"
    return type(value).__name__


def _redact(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): "<redacted>" if str(key).casefold() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value
