from bot.handlers.dm.admin import (
    ai,
    cards,
    characters,
    commands,
    contours,
    inventory,
    panel,
    shakei,
)
from bot.middlewares.auth import AdminRule


def test_all_card_and_character_mutations_are_behind_admin_rule():
    for admin_labeler in (
        ai.labeler,
        cards.labeler,
        characters.labeler,
        commands.labeler,
        contours.labeler,
        inventory.labeler,
        panel.labeler,
        shakei.labeler,
    ):
        assert any(
            isinstance(rule, AdminRule) for rule in admin_labeler.auto_rules
        )
