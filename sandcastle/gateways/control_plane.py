"""ControlPlaneGateway — production. Routes through Sandcastle control plane."""

from __future__ import annotations

import logging
import os
from types import TracebackType
from typing import Any

import httpx

from sandcastle.exceptions import (
    AuthenticationError,
    ConfigurationError,
    CostCapExceededError,
    NetworkError,
    ProviderError,
    SessionNotFoundError,
    ControlPlaneError,
    PathNotAllowedError,
)
from sandcastle.models import (
    LLMResponse,
    Message,
    PresignedURL,
    Role,
    TokenUsage,
    ToolCall,
    Function,
)

logger = logging.getLogger("sandcastle.control_plane")

_ERROR_CODE_MAP: dict[str, type[ControlPlaneError]] = {
    "authentication_failed": AuthenticationError,
    "cost_cap_exceeded":     CostCapExceededError,
    "session_not_found":     SessionNotFoundError,
}


class ControlPlaneGateway:
    """Routes through Sandcastle control plane. Auto-detects env vars in sandbox."""

    def __init__(
        self,
        api_key: str | None = None,
        url: str | None = None,
        session_id: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = (
            api_key
            or os.environ.get("SESSION_TOKEN")
            or os.environ.get("SANDCASTLE_API_KEY")
        )
        self._url = (
            url
            or os.environ.get("CONTROL_PLANE_URL")
            or os.environ.get("SANDCASTLE_CONTROL_PLANE_URL")
        )
        self._session_id = session_id or os.environ.get("SESSION_ID")

        if not self._api_key:
            raise ConfigurationError(
                "No API key found. Provide api_key= or set SANDCASTLE_API_KEY "
                "(outside sandbox) / SESSION_TOKEN (inside sandbox)."
            )
        if not self._url:
            raise ConfigurationError(
                "No control plane URL found. Provide url= or set "
                "SANDCASTLE_CONTROL_PLANE_URL / CONTROL_PLANE_URL."
            )

        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self._url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "X-Sandcastle-SDK": "1.0.0",
            },
            timeout=timeout,
        )

        logger.debug(
            "ControlPlaneGateway initialised url=%s session_id=%s",
            self._url,
            self._session_id or "auto",
        )

    async def __aenter__(self) -> ControlPlaneGateway:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()
        logger.debug("ControlPlaneGateway connection closed")

    async def invoke_llm(
        self,
        new_messages: list[Message],
        tools: list[dict] | None = None,
        tool_choice: str | dict = "auto",
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "new_messages": [m.to_openai_dict() for m in new_messages],
        }
        if self._session_id:
            payload["session_id"] = self._session_id
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        logger.debug(
            "invoke_llm new_messages=%d tools=%s",
            len(new_messages),
            bool(tools),
        )

        data = await self._post("/llm/invoke", payload)
        return self._parse_llm_response(data)

    async def persist_messages(self, messages: list[Message]) -> None:
        payload: dict[str, Any] = {
            "messages": [m.to_openai_dict() for m in messages],
        }
        if self._session_id:
            payload["session_id"] = self._session_id

        await self._post("/messages/persist", payload)
        logger.debug("persist_messages count=%d", len(messages))

    async def request_file_url(
        self,
        file_path: str,
        method: str = "PUT",
    ) -> PresignedURL:
        if not file_path.startswith("/workspace/"):
            raise PathNotAllowedError(file_path)

        payload: dict[str, Any] = {"file_path": file_path, "method": method}
        if self._session_id:
            payload["session_id"] = self._session_id

        data = await self._post("/files/presigned-urls", payload)
        return PresignedURL(
            url=data["url"],
            expires_at=data["expires_at"],
            method=data["method"],
            file_path=data["file_path"],
        )

    async def get_session_cost(self) -> float:
        params = {}
        if self._session_id:
            params["session_id"] = self._session_id

        data = await self._get("/sessions/cost", params)
        return float(data.get("cost_usd", 0.0))

    async def _post(self, path: str, payload: dict) -> dict:
        return await self._request("POST", path, json=payload)

    async def _get(self, path: str, params: dict | None = None) -> dict:
        return await self._request("GET", path, params=params)

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._client.request(method, path, **kwargs)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                logger.warning(
                    "Network error attempt=%d/%d path=%s error=%s",
                    attempt, self._max_retries, path, exc,
                )
                if attempt < self._max_retries:
                    import asyncio
                    await asyncio.sleep(2 ** (attempt - 1))  # Exponential backoff
                continue

            if response.status_code < 400:
                return response.json()

            if 400 <= response.status_code < 500:
                self._raise_4xx(response)

            last_exc = ControlPlaneError(
                f"Control plane error {response.status_code}",
                status_code=response.status_code,
            )
            logger.warning(
                "Server error attempt=%d/%d path=%s status=%d",
                attempt, self._max_retries, path, response.status_code,
            )
            if attempt < self._max_retries:
                import asyncio
                await asyncio.sleep(2 ** (attempt - 1))

        raise NetworkError(
            f"All {self._max_retries} attempts to control plane failed for {path}.",
            attempts=self._max_retries,
            last_status_code=getattr(last_exc, "status_code", None),
        ) from last_exc

    def _raise_4xx(self, response: httpx.Response) -> None:
        try:
            body = response.json()
        except Exception:
            body = {}

        error_code = body.get("error_code", "unknown")
        message = body.get("message", response.text)
        status = response.status_code

        if status == 401 or error_code == "authentication_failed":
            raise AuthenticationError(
                message,
                session_id=body.get("session_id", ""),
                reason=body.get("reason", ""),
            )
        if status == 402 or error_code == "cost_cap_exceeded":
            raise CostCapExceededError(
                message,
                cap_usd=float(body.get("cap_usd", 0)),
                consumed_usd=float(body.get("consumed_usd", 0)),
                session_id=body.get("session_id", ""),
            )
        if status == 404 or error_code == "session_not_found":
            raise SessionNotFoundError(body.get("session_id", "unknown"))

        raise ControlPlaneError(message, status_code=status, error_code=error_code)

    def _parse_llm_response(self, data: dict) -> LLMResponse:
        msg_data = data.get("message", {})
        usage_data = data.get("usage", {})

        tool_calls = None
        if raw_tcs := data.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    function=Function(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                )
                for tc in raw_tcs
            ]

        return LLMResponse(
            message=Message(
                role=Role(msg_data.get("role", "assistant")),
                content=msg_data.get("content", ""),
                tokens=usage_data.get("output_tokens", 0),
            ),
            cost_usd=float(data.get("cost_usd", 0.0)),
            model=data.get("model", "unknown"),
            finish_reason=data.get("finish_reason", "stop"),
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                cached_tokens=usage_data.get("cached_tokens", 0),
            ),
        )
