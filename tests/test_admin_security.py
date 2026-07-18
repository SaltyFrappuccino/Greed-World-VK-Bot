from bot.handlers.dm.admin import cards, characters, panel
from bot.middlewares.auth import AdminRule


def test_all_card_and_character_mutations_are_behind_admin_rule():
    assert any(isinstance(rule, AdminRule) for rule in cards.labeler.auto_rules)
    assert any(isinstance(rule, AdminRule) for rule in characters.labeler.auto_rules)
    assert any(isinstance(rule, AdminRule) for rule in panel.labeler.auto_rules)
