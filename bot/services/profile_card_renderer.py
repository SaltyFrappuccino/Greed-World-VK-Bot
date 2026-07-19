from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from bot.config import get_settings
from bot.services.errors import ServiceError

WIDTH = 1200
HEIGHT = 1600
RENDER_VERSION = 5
STAT_LABELS = (
    ("Стрессоустойчивость", "stress_resistance", "#EF6C8F"),
    ("Речевой аппарат", "speech", "#E89A55"),
    ("Чуйка", "intuition", "#E5C454"),
    ("Хребет", "spine", "#64C58A"),
    ("Воля", "will", "#5CBAD3"),
    ("Нюх", "scent", "#9A7BE1"),
)
RATING_COLORS = {
    "H": "#AAB2BF", "G": "#73B982", "F": "#54BDB2", "E": "#579BDA",
    "D": "#7279E5", "C": "#A26BE0", "B": "#D15DBB", "A": "#F05C91",
    "S": "#FF8156", "SS": "#F4CC58",
}


@dataclass(frozen=True)
class ProfileCardData:
    character_id: int
    name: str
    age: int | None
    gender: str
    rating: str
    shakei: int
    stats: dict[str, int]
    skills: list[str]
    card_counts: dict[str, int]
    contours_used: int
    contour_limit: int
    free_slots_used: int = 0
    free_slot_limit: int = 10
    trophy_ranks: tuple[str, ...] | list[str] = ()


def render_profile_card(data: ProfileCardData, art_bytes: bytes | None) -> bytes:
    regular_path, bold_path = _font_paths()
    fonts = {
        "name": ImageFont.truetype(str(bold_path), 68),
        "subtitle": ImageFont.truetype(str(regular_path), 31),
        "meta": ImageFont.truetype(str(regular_path), 22),
        "meta_bold": ImageFont.truetype(str(bold_path), 22),
        "section": ImageFont.truetype(str(bold_path), 32),
        "body": ImageFont.truetype(str(regular_path), 27),
        "body_bold": ImageFont.truetype(str(bold_path), 27),
        "stat": ImageFont.truetype(str(regular_path), 23),
        "badge": ImageFont.truetype(str(bold_path), 38),
        "small": ImageFont.truetype(str(regular_path), 20),
    }
    image = Image.new("RGB", (WIDTH, HEIGHT), "#09070D")
    _draw_art_header(image, art_bytes, data.name)
    accent = RATING_COLORS.get(data.rating, "#E85BA7")

    _rounded_panel(image, (55, 560, 1145, 735), 34, "#17121D", "#4A2940", 2)
    _rounded_panel(image, (950, 582, 1095, 708), 28, accent)
    draw = ImageDraw.Draw(image)
    _fit_text(
        draw,
        data.name,
        (92, 623),
        800,
        fonts["name"],
        bold_path,
        fill="#FFF7FC",
        anchor="lm",
    )
    _draw_metadata_chips(image, data.age, data.gender, fonts)
    draw = ImageDraw.Draw(image)
    draw.text(
        (1022.5, 645),
        data.rating,
        font=fonts["badge"],
        fill="#160D13",
        anchor="mm",
    )

    _section_title(draw, "СТАТЫ", 790, fonts, accent)
    for index, (label, field, stat_color) in enumerate(STAT_LABELS):
        column = index % 2
        row = index // 2
        x = 65 + column * 555
        y = 850 + row * 105
        _draw_stat(draw, x, y, label, int(data.stats[field]), fonts, stat_color)

    panel_top = 1190
    _rounded_panel(image, (55, panel_top, 1145, 1485), 34, "#151019", "#392636", 2)
    _rounded_panel(image, (800, panel_top + 35, 1110, panel_top + 255), 24, "#211722")
    draw = ImageDraw.Draw(image)
    _section_title(draw, "НАВЫКИ", panel_top + 30, fonts, accent, x=85, line_width=410)
    skills_text = " • ".join(data.skills) if data.skills else "Навыки не указаны"
    _wrapped_text(draw, skills_text, (85, panel_top + 84), 665, fonts["body"], "#E8DDE5", max_lines=5)

    draw.text((830, panel_top + 60), "ПРОГРЕСС", font=fonts["section"], fill=accent)
    draw.text((830, panel_top + 112), f"Шакеи: {data.shakei}", font=fonts["body_bold"], fill="#FFF5FA")
    total_cards = sum(data.card_counts.values())
    draw.text(
        (830, panel_top + 153),
        f"Карты: {total_cards} · Слоты: {data.free_slots_used}/{data.free_slot_limit}",
        font=fonts["meta"],
        fill="#D6C8D2",
    )
    draw.text(
        (830, panel_top + 190),
        f"Контуры: {data.contours_used}/{data.contour_limit}",
        font=fonts["body"],
        fill="#D6C8D2",
    )
    rank_counts = {rank: data.trophy_ranks.count(rank) for rank in ("GOLD", "SILVER", "BRONZE")}
    trophy_y = panel_top + 227
    draw.text(
        (830, trophy_y),
        f"Трофеи: {len(data.trophy_ranks)}",
        font=fonts["small"],
        fill="#D6C8D2",
    )
    draw.text((955, trophy_y), f"З {rank_counts['GOLD']}", font=fonts["small"], fill="#F4CC58")
    draw.text((1010, trophy_y), f"С {rank_counts['SILVER']}", font=fonts["small"], fill="#BFC8D6")
    draw.text((1065, trophy_y), f"Б {rank_counts['BRONZE']}", font=fonts["small"], fill="#C98A55")

    footer = f"ЖАДНЫЙ МИР  •  АНКЕТА #{data.character_id}"
    footer_box = draw.textbbox((0, 0), footer, font=fonts["small"])
    draw.text(((WIDTH - footer_box[2]) / 2, 1540), footer, font=fonts["small"], fill="#8F7C8A")
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _draw_art_header(canvas: Image.Image, art_bytes: bytes | None, name: str) -> None:
    if art_bytes:
        try:
            with Image.open(BytesIO(art_bytes)) as source:
                source_rgb = source.convert("RGB")
                vertical_focus = 0.2 if source_rgb.height > source_rgb.width else 0.45
                header = ImageOps.fit(
                    source_rgb,
                    (WIDTH, 680),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, vertical_focus),
                )
        except OSError as error:
            raise ServiceError(f"Не удалось прочитать основной арт: {error}") from error
    else:
        header = Image.new("RGB", (WIDTH, 680), "#251426")
        draw = ImageDraw.Draw(header)
        for index, color in enumerate(("#7B245E", "#4B255D", "#C23A7B", "#281A4A")):
            x = (index * 317 + len(name) * 41) % 1000
            y = (index * 173 + len(name) * 29) % 480
            draw.ellipse((x - 180, y - 180, x + 300, y + 300), fill=color)
        header = header.filter(ImageFilter.GaussianBlur(45))
    overlay = Image.new("RGBA", header.size, (0, 0, 0, 0))
    pixels = overlay.load()
    for y in range(overlay.height):
        alpha = int(220 * (y / overlay.height) ** 2)
        for x in range(overlay.width):
            pixels[x, y] = (9, 7, 13, alpha)
    canvas.paste(Image.alpha_composite(header.convert("RGBA"), overlay).convert("RGB"), (0, 0))


def _draw_stat(draw, x: int, y: int, label: str, value: int, fonts, color: str) -> None:
    text_center_y = y + 15
    draw.text(
        (x, text_center_y),
        label,
        font=fonts["stat"],
        fill="#D8CBD4",
        anchor="lm",
    )
    for point in range(5):
        left = x + point * 92
        fill = color if point < value else "#332A34"
        draw.rounded_rectangle((left, y + 44, left + 72, y + 60), radius=8, fill=fill)


def _section_title(draw, title: str, y: int, fonts, accent: str, *, x: int = 65, line_width: int = 1015) -> None:
    draw.text((x, y), title, font=fonts["section"], fill=accent)
    draw.rounded_rectangle((x, y + 47, x + line_width, y + 51), radius=2, fill="#3A2634")


def _fit_text(
    draw,
    text: str,
    position,
    max_width: int,
    font,
    bold_path: Path,
    *,
    fill: str,
    anchor: str | None = None,
) -> None:
    current = font
    size = getattr(font, "size", 76)
    while size > 38 and draw.textbbox((0, 0), text, font=current)[2] > max_width:
        size -= 4
        current = ImageFont.truetype(str(bold_path), size)
    draw.text(position, text, font=current, fill=fill, anchor=anchor)


def _draw_metadata_chips(
    canvas: Image.Image,
    age: int | None,
    gender: str,
    fonts,
) -> None:
    items: list[tuple[str, str]] = []
    if age is not None:
        items.append(("Возраст", str(age)))
    if gender.strip():
        items.append(("Пол", gender.strip()))
    if not items:
        items.append(("Данные", "не указаны"))

    measure = ImageDraw.Draw(canvas)
    left = 92
    top = 676
    bottom = 716
    gap = 12
    layouts: list[tuple[int, int, str, str, int]] = []
    for label, value in items:
        label_width = measure.textlength(label, font=fonts["meta"])
        value_width = measure.textlength(value, font=fonts["meta_bold"])
        chip_width = int(label_width + value_width + 47)
        layouts.append((left, left + chip_width, label, value, int(label_width)))
        _rounded_panel(
            canvas,
            (left, top, left + chip_width, bottom),
            18,
            "#261E2A",
            "#3A2C3B",
            1,
        )
        left += chip_width + gap

    draw = ImageDraw.Draw(canvas)
    center_y = (top + bottom) / 2
    for chip_left, _chip_right, label, value, label_width in layouts:
        text_left = chip_left + 16
        draw.text(
            (text_left, center_y),
            label,
            font=fonts["meta"],
            fill="#A99CA6",
            anchor="lm",
        )
        draw.text(
            (text_left + label_width + 9, center_y),
            value,
            font=fonts["meta_bold"],
            fill="#F2E8EF",
            anchor="lm",
        )


def _wrapped_text(draw, text: str, position, max_width: int, font, fill: str, *, max_lines: int) -> None:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    truncated = len(lines) > max_lines
    lines = lines[:max_lines]
    if truncated and lines:
        lines[-1] = _ellipsize(draw, lines[-1], max_width, font)
    x, y = position
    for index, line in enumerate(lines):
        draw.text((x, y + index * 39), line, font=font, fill=fill)


def _ellipsize(draw, text: str, max_width: int, font) -> str:
    base = text.rstrip(".,;: ")
    while base and draw.textbbox((0, 0), base + "…", font=font)[2] > max_width:
        base = base[:-1].rstrip()
    return (base or "") + "…"


def _rounded_panel(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str,
    outline: str | None = None,
    width: int = 1,
) -> None:
    """Нарисовать сглаженную плашку без ступенчатых пикселей на скруглениях."""
    scale = 4
    left, top, right, bottom = box
    panel_width = right - left
    panel_height = bottom - top
    layer = Image.new("RGBA", (panel_width * scale, panel_height * scale))
    layer_draw = ImageDraw.Draw(layer)
    inset = max(1, width * scale // 2)
    layer_draw.rounded_rectangle(
        (inset, inset, panel_width * scale - inset - 1, panel_height * scale - inset - 1),
        radius=radius * scale,
        fill=fill,
        outline=outline,
        width=max(1, width * scale),
    )
    layer = layer.resize((panel_width, panel_height), Image.Resampling.LANCZOS)
    canvas.paste(layer, (left, top), layer)


def _font_paths() -> tuple[Path, Path]:
    settings = get_settings()
    regular = _first_font(
        settings.profile_card_font_regular,
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    )
    bold = _first_font(
        settings.profile_card_font_bold,
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    )
    return regular, bold


def _first_font(*candidates: str | None) -> Path:
    for raw_path in candidates:
        if raw_path and Path(raw_path).is_file():
            return Path(raw_path)
    raise ServiceError(
        "Не найден шрифт с поддержкой кириллицы. Укажите PROFILE_CARD_FONT_REGULAR "
        "и PROFILE_CARD_FONT_BOLD в .env."
    )
