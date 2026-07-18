from datetime import datetime
from io import BytesIO

from openpyxl import load_workbook

from bot.database.models import Card, CardOwnership, CardType, Rarity
from bot.services.spreadsheet_service import (
    _build_sync,
    _character_sheet,
    _registry_sheet,
)


def test_character_export_has_four_category_friendly_fields():
    ordinary = CardOwnership(
        card_id=None,
        character_id=1,
        ordinary_name="Верёвка",
        ordinary_kind="Инструмент",
        ordinary_description="Десять метров",
        ordinary_usage="Связать предметы",
        ordinary_rarity=Rarity.H,
        obtained_at=datetime(2026, 7, 18, 12, 30),
    )

    sheet = _character_sheet("Ава", [ordinary], CardType.ORDINARY, "Обычные")

    assert sheet["name"] == "Обычные"
    assert sheet["rows"][0][0] == ""
    assert sheet["rows"][0][1:4] == ["Верёвка", "Инструмент", "H"]
    assert sheet["dateColumns"] == [6]


def test_registry_export_uses_correct_game_number_and_vk_link():
    card = Card(
        id=41,
        name="Искра",
        card_type=CardType.SPELL,
        registry_number=0,
        kind="Заклинание",
        rarity=Rarity.H,
        description="Свет",
        usage="Назвать карту",
        copies_count=2,
        created_by=564059694,
        created_at=datetime(2026, 7, 18, 12, 30),
    )

    sheet = _registry_sheet([card], CardType.SPELL, "Заклинания")

    assert sheet["rows"][0][0:3] == [0, 41, "Искра"]
    assert sheet["rows"][0][-1] == "https://vk.ru/id564059694"


def test_xlsx_is_built_with_openpyxl_tables_dates_and_freeze_panes():
    received_at = datetime(2026, 7, 18, 12, 30)
    definition = {
        "name": "Обычные",
        "title": "Карты персонажа «Ава» — Обычные",
        "subtitle": "Всего физических копий в категории: 1",
        "headers": ["Название", "Дата получения"],
        "rows": [["Верёвка", received_at]],
        "dateColumns": [1],
        "widths": [24, 20],
    }

    export = _build_sync("cards.xlsx", [definition])
    workbook = load_workbook(BytesIO(export.data))
    sheet = workbook["Обычные"]

    assert export.filename == "cards.xlsx"
    assert sheet["A1"].value == "Карты персонажа «Ава» — Обычные"
    assert sheet["B4"].value == received_at
    assert sheet["B4"].number_format == "dd.mm.yyyy hh:mm"
    assert sheet.freeze_panes == "A4"
    assert sheet.sheet_view.showGridLines is False
    assert list(sheet.tables) == ["CardsTable1"]
