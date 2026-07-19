"""Совместимый фасад модульного административного AI-агента."""

from bot.services import auth_service
from bot.services.admin_ai.orchestrator import process_message
from bot.services.admin_ai.planning import (
    cancel_plan,
    confirm_plan,
    create_plan,
    format_plan,
    format_result,
    mark_plan_failed,
)
from bot.services.admin_ai.read_tools import READ_TOOLS, _run_read_tool
from bot.services.admin_ai.runtime import AssistantAttachment, AssistantOutcome
from bot.services.admin_ai.sessions import (
    close_session,
    history_text,
    open_session,
    start_new_session,
)
from bot.services.admin_ai.values import WRITE_TOOLS

__all__ = [
    "AssistantAttachment",
    "AssistantOutcome",
    "READ_TOOLS",
    "WRITE_TOOLS",
    "auth_service",
    "cancel_plan",
    "close_session",
    "confirm_plan",
    "create_plan",
    "format_plan",
    "format_result",
    "history_text",
    "mark_plan_failed",
    "open_session",
    "process_message",
    "start_new_session",
]
