from bot.handlers.dm.admin import (
    ai,
    arts,
    book_slots,
    assistant,
    cards,
    characters,
    commands,
    contours,
    inventory,
    panel,
    shakei,
    trophies,
)

labelers = [
    commands.labeler,
    arts.labeler,
    book_slots.labeler,
    assistant.labeler,
    contours.labeler,
    inventory.labeler,
    cards.labeler,
    characters.labeler,
    shakei.labeler,
    trophies.labeler,
    ai.labeler,
    panel.labeler,
]
