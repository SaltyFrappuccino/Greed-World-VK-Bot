from bot.handlers.dm import cards, character, character_registry, contours, menu, shakei

control_labeler = menu.labeler
labelers = [
    cards.labeler,
    character.labeler,
    character_registry.labeler,
    contours.labeler,
    shakei.labeler,
]
fallback_labeler = menu.fallback_labeler
