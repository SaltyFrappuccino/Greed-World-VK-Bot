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

labelers = [
    commands.labeler,
    contours.labeler,
    inventory.labeler,
    cards.labeler,
    characters.labeler,
    shakei.labeler,
    ai.labeler,
    panel.labeler,
]
