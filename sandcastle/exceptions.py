"""SDK exceptions. Root: SandcastleError. Catch broadly or by subtype."""

from __future__ import annotations


class SandcastleError(Exception):
    pass


class GatewayError(SandcastleError):
    """Raised when a gateway communication operation fails."""


class ControlPlaneError(GatewayError):
    def __init__(
        self,
        message: str,
        status_code: int = 0,
        error_code: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class AuthenticationError(ControlPlaneError):
    def __init__(self, message: str, session_id: str = "", reason: str = "") -> None:
        super().__init__(message, status_code=401, error_code="authentication_failed")
        self.session_id = session_id
        self.reason = reason


class CostCapExceededError(ControlPlaneError):
    def __init__(
        self,
        message: str,
        cap_usd: float = 0.0,
        consumed_usd: float = 0.0,
        session_id: str = "",
    ) -> None:
        super().__init__(message, status_code=402, error_code="cost_cap_exceeded")
        self.cap_usd = cap_usd
        self.consumed_usd = consumed_usd
        self.session_id = session_id


class SessionNotFoundError(ControlPlaneError):
    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Session '{session_id}' not found or already terminated.",
            status_code=404,
            error_code="session_not_found",
        )
        self.session_id = session_id


class NetworkError(GatewayError):
    def __init__(
        self,
        message: str,
        attempts: int = 0,
        last_status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_status_code = last_status_code


class LLMError(SandcastleError):
    """Raised when the LLM provider returns an error."""


class RateLimitError(LLMError):
    def __init__(
        self,
        message: str,
        retry_after_seconds: int = 60,
        provider: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.provider = provider


class ContentPolicyError(LLMError):
    pass


class ProviderError(LLMError):
    pass


class FileError(SandcastleError):
    pass


class PathNotAllowedError(FileError):
    def __init__(self, attempted_path: str, allowed_prefix: str = "/workspace/") -> None:
        super().__init__(
            f"Path '{attempted_path}' is not allowed. "
            f"File paths must start with '{allowed_prefix}'."
        )
        self.attempted_path = attempted_path
        self.allowed_prefix = allowed_prefix


class PresignedURLExpiredError(FileError):
    def __init__(self, file_path: str, expired_at: str) -> None:
        super().__init__(
            f"Presigned URL for '{file_path}' expired at {expired_at}. "
            "Request a new URL via gateway.request_file_url()."
        )
        self.file_path = file_path
        self.expired_at = expired_at


class ConfigurationError(SandcastleError):
    pass
