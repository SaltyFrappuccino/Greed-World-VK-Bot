from math import ceil


PAGE_SIZE = 8


def normalize_page(requested: int, total: int, page_size: int = PAGE_SIZE) -> tuple[int, int]:
    pages = max(1, ceil(total / page_size))
    page = min(max(requested, 0), pages - 1)
    return page, pages
