from bot.handlers.dm.admin import ai, cards, characters, panel, shakei

labelers = [
    cards.labeler,
    characters.labeler,
    shakei.labeler,
    ai.labeler,
    panel.labeler,
]
