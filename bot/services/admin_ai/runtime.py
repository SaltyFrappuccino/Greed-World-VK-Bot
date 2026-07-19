from dataclasses import dataclass

from bot.database.models import AdminAIPlan


@dataclass(frozen=True)
class AssistantAttachment:
    filename: str
    data: bytes
    kind: str = "document"


@dataclass(frozen=True)
class AssistantOutcome:
    text: str
    plan: AdminAIPlan | None = None
    attachments: tuple[AssistantAttachment, ...] = ()
