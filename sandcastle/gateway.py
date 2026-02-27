"""AgentGateway protocol — implement these four async methods."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sandcastle.models import LLMResponse, Message, PresignedURL


@runtime_checkable
class AgentGateway(Protocol):
    async def invoke_llm(
        self,
        new_messages: list[Message],
        tools: list[dict] | None = None,
        tool_choice: str | dict = "auto",
    ) -> LLMResponse:
        ...

    async def persist_messages(self, messages: list[Message]) -> None:
        ...

    async def request_file_url(
        self,
        file_path: str,
        method: str = "PUT",
    ) -> PresignedURL:
        ...

    async def get_session_cost(self) -> float:
        ...
