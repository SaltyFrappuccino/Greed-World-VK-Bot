"""Public facade for content generation and the admin AI protocol."""

from bot.database.models import CardType, Rarity
from bot.services.admin_ai.contracts import (
    AdminAssistantTurn,
    AssistantAction,
    AssistantToolCall,
)
from bot.services.admin_ai.llm import generate_admin_assistant_turn
from bot.services.content_ai.cards import generate_card
from bot.services.content_ai.character import character_fields, generate_character
from bot.services.content_ai.contracts import CardDraft, CharacterDraft, ContourDraft
from bot.services.content_ai.contours import contour_fields, generate_contour
from bot.services.content_ai.previews import card_preview, character_preview, contour_preview
from bot.services.errors import ServiceError, ValidationError

__all__ = [
    "AdminAssistantTurn",
    "AssistantAction",
    "AssistantToolCall",
    "CardDraft",
    "CardType",
    "CharacterDraft",
    "ContourDraft",
    "Rarity",
    "ServiceError",
    "ValidationError",
    "card_preview",
    "character_fields",
    "character_preview",
    "contour_fields",
    "contour_preview",
    "generate_admin_assistant_turn",
    "generate_card",
    "generate_character",
    "generate_contour",
]
