from bot.handlers.dm.admin import (
    ai,
    assistant,
    book_slots,
    cards,
    characters,
    commands,
    contours,
    inventory,
    panel,
    shakei,
    trophies,
)
from bot.handlers.chat import trophies as chat_trophies
from bot.middlewares.auth import AdminRule


def test_all_card_and_character_mutations_are_behind_admin_rule():
    for admin_labeler in (
        ai.labeler,
        assistant.labeler,
        book_slots.labeler,
        cards.labeler,
        characters.labeler,
        commands.labeler,
        contours.labeler,
        inventory.labeler,
        panel.labeler,
        shakei.labeler,
        trophies.labeler,
        chat_trophies.admin_labeler,
    ):
        assert any(
            isinstance(rule, AdminRule) for rule in admin_labeler.auto_rules
        )
