import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssistantToolCall(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    arguments: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_arguments(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        result = dict(value)
        arguments = result.get("arguments")
        if arguments is None:
            result["arguments"] = {}
        elif isinstance(arguments, str):
            try:
                result["arguments"] = json.loads(arguments)
            except json.JSONDecodeError:
                pass
        return result


class AssistantAction(AssistantToolCall):
    description: str = ""


class AdminAssistantTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["answer", "clarification", "read_tools", "action_plan"]
    message: str = ""
    tools: list[AssistantToolCall] = Field(default_factory=list)
    actions: list[AssistantAction] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_shape(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        result = dict(value)
        if "kind" not in result and "type" in result:
            result["kind"] = result["type"]
        if "message" not in result:
            result["message"] = result.get("answer", result.get("question", ""))
        for field in ("tools", "actions", "warnings"):
            if result.get(field) is None:
                result[field] = []
        return result


def parse_turn(content: str) -> AdminAssistantTurn:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    return AdminAssistantTurn.model_validate(data)
