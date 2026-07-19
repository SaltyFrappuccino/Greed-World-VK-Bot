from bot.handlers.dm import arts, cards, character, character_registry, contours, menu, shakei, trophies

control_labeler = menu.labeler
labelers = [
    arts.labeler,
    cards.labeler,
    character.labeler,
    character_registry.labeler,
    contours.labeler,
    shakei.labeler,
    trophies.labeler,
]
fallback_labeler = menu.fallback_labeler
