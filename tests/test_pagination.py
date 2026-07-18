from bot.utils.pagination import normalize_page


def test_pagination_clamps_page_and_always_has_one_page():
    assert normalize_page(-5, 0) == (0, 1)
    assert normalize_page(50, 17, page_size=8) == (2, 3)
    assert normalize_page(1, 17, page_size=8) == (1, 3)
