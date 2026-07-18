import asyncio
from io import BytesIO
from dataclasses import dataclass
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import characters as characters_crud
from bot.database.models import Card, CardOwnership, CardType
from bot.services.errors import NotFoundError, ServiceError


@dataclass(frozen=True)
class SpreadsheetExport:
    filename: str
    data: bytes


async def export_character_cards(
    session: AsyncSession, character_id: int
) -> SpreadsheetExport:
    character = await characters_crud.get_by_id(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    ownerships = await cards_crud.list_character_ownerships(session, character_id)
    sheets = [
        _character_sheet(character.name, ownerships, card_type, title)
        for card_type, title in (
            (CardType.SPECIAL, "Особые слоты"),
            (CardType.SPELL, "Заклинания"),
            (CardType.CONTOUR, "Контурные"),
            (CardType.ORDINARY, "Обычные"),
        )
    ]
    filename = f"cards_character_{character.id}_{datetime.now():%Y-%m-%d_%H-%M-%S}.xlsx"
    return await _build(filename, sheets)


async def export_registry(session: AsyncSession) -> SpreadsheetExport:
    cards = await cards_crud.list_cards(
        session,
        limit=100_000,
        card_types=(CardType.SPECIAL, CardType.SPELL, CardType.CONTOUR),
    )
    sheets = [
        _registry_sheet(cards, card_type, title)
        for card_type, title in (
            (CardType.SPECIAL, "Особые слоты"),
            (CardType.SPELL, "Заклинания"),
            (CardType.CONTOUR, "Контурные"),
        )
    ]
    filename = f"cards_registry_{datetime.now():%Y-%m-%d_%H-%M-%S}.xlsx"
    return await _build(filename, sheets)


def _character_sheet(
    character_name: str,
    ownerships: list[CardOwnership],
    card_type: CardType,
    title: str,
) -> dict[str, object]:
    selected = [item for item in ownerships if item.display_type is card_type]
    headers = [
        "Игровой номер",
        "Название",
        "Вид / подтип",
        "Редкость",
        "Описание",
        "Способ использования",
        "Дата получения",
        "Статус",
    ]
    rows = []
    for ownership in selected:
        card = ownership.card
        game_number: int | str = ""
        if card is not None:
            game_number = (
                card.number
                if card.card_type is CardType.SPECIAL
                else card.registry_number if card.registry_number is not None else ""
            )
        status = (
            f"Связана: Контур #{ownership.contour_component.contour_id}"
            if ownership.contour_component is not None
            else "Свободна"
        )
        rows.append(
            [
                game_number,
                ownership.display_name,
                ownership.display_kind,
                ownership.display_rarity.value,
                ownership.display_description,
                ownership.display_usage,
                _excel_datetime(ownership.obtained_at),
                status,
            ]
        )
    return {
        "name": title,
        "title": f"Карты персонажа «{character_name}» — {title}",
        "subtitle": f"Всего физических копий в категории: {len(rows)}",
        "headers": headers,
        "rows": rows,
        "dateColumns": [6],
        "widths": [14, 24, 22, 10, 42, 42, 20, 22],
    }


def _registry_sheet(
    cards: list[Card], card_type: CardType, title: str
) -> dict[str, object]:
    selected = [card for card in cards if card.card_type is card_type]
    headers = [
        "Игровой номер",
        "ID БД",
        "Название",
        "Вид / подтип",
        "Редкость",
        "Описание",
        "Способ использования",
        "Лимит преобразований",
        "Живых копий",
        "Создана",
        "Создал VK",
    ]
    rows = [
        [
            card.number if card_type is CardType.SPECIAL else card.registry_number,
            card.id,
            card.name,
            card.kind,
            card.rarity.value,
            card.description,
            card.usage,
            card.transform_limit if card.transform_limit is not None else "Без лимита",
            card.copies_count,
            _excel_datetime(card.created_at),
            f"https://vk.ru/id{card.created_by}",
        ]
        for card in selected
    ]
    return {
        "name": title,
        "title": f"Реестр карт — {title}",
        "subtitle": f"Всего карт в категории: {len(rows)}",
        "headers": headers,
        "rows": rows,
        "dateColumns": [9],
        "widths": [14, 10, 24, 22, 10, 42, 42, 20, 14, 20, 28],
    }


async def _build(
    filename: str, sheets: list[dict[str, object]]
) -> SpreadsheetExport:
    try:
        return await asyncio.to_thread(_build_sync, filename, sheets)
    except (OSError, ValueError) as error:
        raise ServiceError(f"Не удалось создать XLSX: {error}") from error


def _build_sync(
    filename: str,
    sheets: list[dict[str, object]],
) -> SpreadsheetExport:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for index, definition in enumerate(sheets, start=1):
        _add_sheet(workbook, definition, index)
    stream = BytesIO()
    workbook.save(stream)
    return SpreadsheetExport(filename=filename, data=stream.getvalue())


def _add_sheet(workbook: Workbook, definition: dict[str, object], index: int) -> None:
    sheet = workbook.create_sheet(str(definition["name"]))
    headers = list(definition["headers"])
    rows = list(definition["rows"])
    widths = list(definition["widths"])
    date_columns = set(definition["dateColumns"])
    last_column = get_column_letter(len(headers))

    sheet.merge_cells(f"A1:{last_column}1")
    sheet["A1"] = str(definition["title"])
    sheet["A1"].fill = PatternFill("solid", fgColor="6D174D")
    sheet["A1"].font = Font(name="Aptos Display", size=16, bold=True, color="FFFFFF")
    sheet["A1"].alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 30

    sheet.merge_cells(f"A2:{last_column}2")
    sheet["A2"] = str(definition.get("subtitle", ""))
    sheet["A2"].fill = PatternFill("solid", fgColor="F5E7F0")
    sheet["A2"].font = Font(name="Aptos", italic=True, color="4A1538")
    sheet["A2"].alignment = Alignment(vertical="center", wrap_text=True)
    sheet.row_dimensions[2].height = 28

    header_fill = PatternFill("solid", fgColor="B52B7B")
    header_border = Border(bottom=Side(style="thin", color="7A1D57"))
    for column, value in enumerate(headers, start=1):
        cell = sheet.cell(row=3, column=column, value=value)
        cell.fill = header_fill
        cell.font = Font(name="Aptos", bold=True, color="FFFFFF")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = header_border
    sheet.row_dimensions[3].height = 30

    if rows:
        for row_index, values in enumerate(rows, start=4):
            for column_index, value in enumerate(values, start=1):
                cell = sheet.cell(row=row_index, column=column_index, value=value)
                cell.font = Font(name="Aptos", size=10)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                if column_index - 1 in date_columns and value:
                    cell.number_format = "dd.mm.yyyy hh:mm"
                if isinstance(value, str) and value.startswith("https://vk.ru/"):
                    cell.hyperlink = value
                    cell.style = "Hyperlink"
            sheet.row_dimensions[row_index].height = _content_row_height(
                values, widths
            )
        table = Table(
            displayName=f"CardsTable{index}",
            ref=f"A3:{last_column}{len(rows) + 3}",
        )
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium4",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        sheet.add_table(table)
    else:
        sheet.merge_cells(f"A4:{last_column}4")
        sheet["A4"] = "Карт в этой категории пока нет"
        sheet["A4"].fill = PatternFill("solid", fgColor="FAF6F9")
        sheet["A4"].font = Font(name="Aptos", italic=True, color="6B5A65")
        sheet["A4"].alignment = Alignment(vertical="center")

    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = min(
            float(width), 45
        )
    sheet.freeze_panes = "A4"
    sheet.sheet_view.showGridLines = False
    if not rows:
        sheet.auto_filter.ref = f"A3:{last_column}3"
    sheet.print_title_rows = "1:3"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True


def _excel_datetime(value: datetime | None) -> datetime | str:
    if value is None:
        return ""
    return value.replace(tzinfo=None)


def _content_row_height(values: list[object], widths: list[object]) -> float:
    line_count = 1
    for value, width in zip(values, widths, strict=False):
        if value in (None, ""):
            continue
        text = str(value)
        column_width = max(float(width), 1)
        wrapped_lines = sum(
            max(1, (len(part) + int(column_width) - 1) // int(column_width))
            for part in text.splitlines() or [""]
        )
        line_count = max(line_count, wrapped_lines)
    return min(max(18, line_count * 15), 120)
