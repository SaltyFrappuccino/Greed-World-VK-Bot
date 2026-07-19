from bot.handlers.chat import assistant, card_usage, commands, dice, profile_card, trophies

labelers = [
    trophies.admin_labeler,
    trophies.labeler,
    assistant.public_labeler,
    assistant.labeler,
    card_usage.labeler,
    profile_card.labeler,
    commands.labeler,
    dice.labeler,
]
