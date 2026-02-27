"""MockGateway — test double for AgentGateway. No network calls."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from sandcastle.models import LLMResponse, Message, PresignedURL


class MockGatewayQueueEmptyError(Exception):
    pass


class MockGateway:

    def __init__(
        self,
        responses: list[LLMResponse] | None = None,
        default_response: LLMResponse | None = None,
        workspace_dir: str = "/tmp/sandcastle-mock-workspace",
    ) -> None:
        self._queue: deque[LLMResponse] = deque(responses or [])
        self._default = default_response
        self._workspace = workspace_dir

        self._invoke_calls: list[dict] = []
        self._persist_calls: list[list[Message]] = []
        self._file_url_calls: list[dict] = []

        self._total_cost: float = 0.0

    def queue_response(self, response: LLMResponse) -> None:
        self._queue.append(response)

    def queue_responses(self, responses: list[LLMResponse]) -> None:
        self._queue.extend(responses)

    def _next_response(self) -> LLMResponse:
        if self._queue:
            return self._queue.popleft()
        if self._default is not None:
            return self._default
        raise MockGatewayQueueEmptyError(
            "MockGateway response queue is empty and no default_response was set. "
            "Call mock.queue_response() to add more responses."
        )

    async def invoke_llm(
        self,
        new_messages: list[Message],
        tools: list[dict] | None = None,
        tool_choice: str | dict = "auto",
    ) -> LLMResponse:
        self._invoke_calls.append({
            "new_messages": new_messages,
            "tools": tools,
            "tool_choice": tool_choice,
        })
        response = self._next_response()
        self._total_cost += response.cost_usd
        return response

    async def persist_messages(self, messages: list[Message]) -> None:
        self._persist_calls.append(list(messages))

    async def request_file_url(
        self,
        file_path: str,
        method: str = "PUT",
    ) -> PresignedURL:
        from pathlib import Path
        self._file_url_calls.append({"file_path": file_path, "method": method})
        resolved = Path(self._workspace) / file_path.removeprefix("/workspace/")
        expiry = datetime.now(timezone.utc).replace(hour=23, minute=59).isoformat()
        return PresignedURL(
            url=resolved.as_uri(),
            expires_at=expiry,
            method=method,
            file_path=file_path,
        )

    async def get_session_cost(self) -> float:
        return self._total_cost

    @property
    def invoke_llm_call_count(self) -> int:
        return len(self._invoke_calls)

    @property
    def persist_messages_call_count(self) -> int:
        return len(self._persist_calls)

    @property
    def file_url_request_count(self) -> int:
        return len(self._file_url_calls)

    @property
    def total_messages_sent(self) -> int:
        return sum(len(c["new_messages"]) for c in self._invoke_calls)

    @property
    def last_request(self) -> dict | None:
        return self._invoke_calls[-1] if self._invoke_calls else None

    @property
    def all_invoke_calls(self) -> list[dict]:
        return list(self._invoke_calls)

    @property
    def all_persisted_messages(self) -> list[Message]:
        return [m for batch in self._persist_calls for m in batch]

    def reset(self) -> None:
        self._invoke_calls.clear()
        self._persist_calls.clear()
        self._file_url_calls.clear()
        self._total_cost = 0.0
