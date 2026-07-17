from bot.utils.messages import split_message


def test_split_message_keeps_every_chunk_within_limit():
    text = "Первый раздел\n" + "А" * 25 + "\nПоследний раздел"

    chunks = split_message(text, limit=12)

    assert all(len(chunk) <= 12 for chunk in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")
