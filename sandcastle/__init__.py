"""sandcastle-sdk — AgentGateway protocol for agent execution."""

from sandcastle.gateway import AgentGateway
from sandcastle.gateways.control_plane import ControlPlaneGateway
from sandcastle.gateways.direct import DirectGateway
from sandcastle.models import (
    Function,
    LLMResponse,
    Message,
    PresignedURL,
    Role,
    TokenUsage,
    ToolCall,
)

__version__ = "1.0.0"
__author__ = "Gold Okpa"
__license__ = "MIT"

__all__ = [
    "AgentGateway",
    "DirectGateway",
    "ControlPlaneGateway",
    "Message",
    "Role",
    "LLMResponse",
    "PresignedURL",
    "TokenUsage",
    "ToolCall",
    "Function",
    "__version__",
]
