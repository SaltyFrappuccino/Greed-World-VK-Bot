from bot.services.admin_ai.diagnostics import response_shape, safe_json


def test_safe_json_redacts_secrets() -> None:
    result = safe_json(
        {"query": "Пикколо", "api_key": "secret", "nested": {"token": "hidden"}}
    )

    assert "Пикколо" in result
    assert "secret" not in result
    assert "hidden" not in result
    assert result.count("<redacted>") == 2


def test_response_shape_describes_invalid_agent_payload_without_body() -> None:
    result = response_shape(
        '{"kind":"read_tools","message":"private","tools":{},"actions":[]}'
    )

    assert "shape=" in result
    assert '"tools": "dict[0]"' in result
    assert "private" not in result
