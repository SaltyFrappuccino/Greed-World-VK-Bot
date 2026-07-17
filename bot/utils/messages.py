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


async def answer_long(message: Any, text: str, *, keyboard: str | None = None) -> None:
    chunks = split_message(text)
    for chunk in chunks[:-1]:
        await message.answer(chunk)
    await message.answer(chunks[-1], keyboard=keyboard)
