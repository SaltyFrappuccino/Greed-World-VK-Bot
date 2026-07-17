def test_chat_handlers_use_question_exclamation_prefix(monkeypatch):
    monkeypatch.setenv("VK_COMMUNITY_TOKEN", "test")
    monkeypatch.setenv("VK_GROUP_ID", "1")

    from bot.handlers.chat import commands, dice

    patterns = [
        pattern
        for labeler in (commands.labeler, dice.labeler)
        for handler in labeler.message_view.handlers
        for rule in handler.rules
        if type(rule).__name__ == "VBMLRule"
        for pattern in rule.patterns
    ]
    expected = {
        "?!карта",
        "?!карта Ясень",
        "?!профиль",
        "?!профиль Ава",
        "?!кубик",
        "?!кубик 1 20",
        "?!помощь",
    }

    for command in expected:
        assert any(pattern.compiler.fullmatch(command) for pattern in patterns)

    assert not any(pattern.compiler.fullmatch("!карта Ясень") for pattern in patterns)
