from bot.handlers.dm import cards, character, menu, shakei

control_labeler = menu.labeler
labelers = [cards.labeler, character.labeler, shakei.labeler]
fallback_labeler = menu.fallback_labeler
