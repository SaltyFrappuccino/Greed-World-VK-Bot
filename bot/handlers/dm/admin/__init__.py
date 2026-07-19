from bot.handlers.dm.admin import (
    ai,
    arts,
    assistant,
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
    arts.labeler,
    assistant.labeler,
    contours.labeler,
    inventory.labeler,
    cards.labeler,
    characters.labeler,
    shakei.labeler,
    ai.labeler,
    panel.labeler,
]
