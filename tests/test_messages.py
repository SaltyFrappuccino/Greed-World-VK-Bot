from unittest.mock import AsyncMock

import pytest

from bot.utils.messages import answer_long


@pytest.mark.asyncio
async def test_answer_long_attaches_image_to_single_profile_message():
    message = type("Message", (), {"answer": AsyncMock()})()

    await answer_long(
        message,
        "Профиль персонажа",
        keyboard="profile-keyboard",
        attachment="photo-1_2_key",
    )

    message.answer.assert_awaited_once_with(
        "Профиль персонажа",
        attachment="photo-1_2_key",
        keyboard="profile-keyboard",
    )


@pytest.mark.asyncio
async def test_answer_long_attaches_image_only_to_first_chunk():
    message = type("Message", (), {"answer": AsyncMock()})()

    await answer_long(
        message,
        "A" * 3501,
        keyboard="profile-keyboard",
        attachment="photo-1_2_key",
    )

    assert message.answer.await_count == 2
    assert message.answer.await_args_list[0].args == ("A" * 3500,)
    assert message.answer.await_args_list[0].kwargs == {
        "attachment": "photo-1_2_key"
    }
    assert message.answer.await_args_list[1].args == ("A",)
    assert message.answer.await_args_list[1].kwargs == {
        "keyboard": "profile-keyboard"
    }
