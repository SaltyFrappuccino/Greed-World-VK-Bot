from vkbottle import Keyboard, KeyboardButtonColor, Text


def _add_pager(
    keyboard: Keyboard, command: str, page: int, pages: int
) -> None:
    if page > 0:
        keyboard.add(Text("←", payload={"cmd": command, "page": page - 1}))
    keyboard.add(
        Text(
            f"Страница {page + 1}/{pages}",
            payload={"cmd": command, "page": page},
        ),
        color=KeyboardButtonColor.SECONDARY,
    )
    if page + 1 < pages:
        keyboard.add(Text("→", payload={"cmd": command, "page": page + 1}))


def _short_label(text: str, limit: int = 36) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

