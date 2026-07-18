from bot.handlers.dm import cards, character, character_registry, menu, shakei

control_labeler = menu.labeler
labelers = [cards.labeler, character.labeler, character_registry.labeler, shakei.labeler]
fallback_labeler = menu.fallback_labeler
