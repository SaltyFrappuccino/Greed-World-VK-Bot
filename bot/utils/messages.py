from typing import Any


VK_MESSAGE_LIMIT = 3500


def split_message(text: str, limit: int = VK_MESSAGE_LIMIT) -> list[str]:
    """Разбить длинную анкету по строкам, не превышая безопасный лимит VK."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.append(line[:limit].rstrip())
            line = line[limit:]
        if current and len(current) + len(line) > limit:
            chunks.append(current.rstrip())
            current = ""
        current += line
    if current or not chunks:
        chunks.append(current.rstrip())
    return chunks


async def answer_long(
    message: Any,
    text: str,
    *,
    keyboard: str | None = None,
    attachment: str | None = None,
) -> None:
    chunks = split_message(text)
    for index, chunk in enumerate(chunks):
        params: dict[str, str] = {}
        if index == 0 and attachment:
            params["attachment"] = attachment
        if index == len(chunks) - 1 and keyboard:
            params["keyboard"] = keyboard
        await message.answer(chunk, **params)
