"""Core data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class Message:
    role: Role
    content: str | list[dict[str, Any]]
    tool_call_id: str | None = None
    name: str | None = None
    tokens: int = 0

    def to_openai_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d


@dataclass
class Function:
    name: str
    arguments: str  # JSON-encoded string


@dataclass
class ToolCall:
    id: str
    function: Function
    type: str = "function"


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_tokens: int = 0


@dataclass
class LLMResponse:
    message: Message
    cost_usd: float
    model: str
    finish_reason: str
    tool_calls: list[ToolCall] | None = None
    usage: TokenUsage = field(
        default_factory=lambda: TokenUsage(
            input_tokens=0, output_tokens=0, total_tokens=0
        )
    )


@dataclass
class PresignedURL:
    url: str
    expires_at: str
    method: str
    file_path: str
