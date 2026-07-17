def test_global_cancel_is_registered_before_state_handlers(monkeypatch):
    monkeypatch.setenv("VK_COMMUNITY_TOKEN", "test")
    monkeypatch.setenv("VK_GROUP_ID", "1")

    from bot.config import get_settings
    from bot.main import create_bot

    get_settings.cache_clear()
    handlers = create_bot().labeler.message_view.handlers
    cancel_index = next(
        index for index, handler in enumerate(handlers) if handler.handler.__name__ == "cancel"
    )
    state_indexes = [
        index
        for index, handler in enumerate(handlers)
        if any(type(rule).__name__ == "StateRule" for rule in handler.rules)
    ]

    assert state_indexes
    assert cancel_index < min(state_indexes)
