from bot.handlers.chat import card_usage, commands, dice, profile_card, trophies

labelers = [
    trophies.admin_labeler,
    trophies.labeler,
    card_usage.labeler,
    profile_card.labeler,
    commands.labeler,
    dice.labeler,
]
