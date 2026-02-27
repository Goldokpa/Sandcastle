# sandcastle-sdk

AgentGateway protocol for AI agent execution.

[![CI](https://github.com/Goldokpa/Sandcastle/actions/workflows/ci.yml/badge.svg)](https://github.com/Goldokpa/Sandcastle/actions)
[![PyPI](https://img.shields.io/pypi/v/sandcastle-sdk)](https://pypi.org/project/sandcastle-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/sandcastle-sdk)](https://pypi.org/project/sandcastle-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## The problem

Agents that run code or call APIs need an environment. That environment usually has API keys, DB creds, cloud tokens. Running the agent on the same backend as your API means the agent can access every secret, and redeploying kills all agents.

## How it works

Two gateway implementations:

| Gateway | When to use | Credentials | History |
|---|---|---|---|
| `DirectGateway` | Local dev, CI | Your API key | In-memory |
| `ControlPlaneGateway` | Production | None in agent | Control plane |

## Quick start

```bash
pip install sandcastle-sdk[openai]
```

```python
import asyncio
from openai import AsyncOpenAI
from sandcastle import DirectGateway, Message, Role

async def main():
    gateway = DirectGateway(
        llm_client=AsyncOpenAI(),
        model="gpt-4o",
    )

    response = await gateway.invoke_llm(
        new_messages=[Message(role=Role.USER, content="Hello, Sandcastle!")]
    )

    print(response.message.content)
    print(f"Cost: ${response.cost_usd:.6f}")

asyncio.run(main())
```

### Production

```python
from sandcastle import ControlPlaneGateway
gateway = ControlPlaneGateway()  # env vars in sandbox
```

## Installation

```bash
# Core SDK only
pip install sandcastle-sdk

# With OpenAI support
pip install sandcastle-sdk[openai]

# With Anthropic support
pip install sandcastle-sdk[anthropic]

# Both providers
pip install sandcastle-sdk[all]
```

Python 3.10+

## Protocol

Implement these four async methods:

```python
class AgentGateway(Protocol):
    async def invoke_llm(self, new_messages, tools=None, tool_choice="auto") -> LLMResponse: ...
    async def persist_messages(self, messages) -> None: ...
    async def request_file_url(self, file_path, method="PUT") -> PresignedURL: ...
    async def get_session_cost(self) -> float: ...
```

## Testing

```python
from sandcastle.testing import MockGateway
from sandcastle.models import LLMResponse, Message, Role

async def test_my_agent():
    mock = MockGateway()
    mock.queue_response(LLMResponse(
        message=Message(role=Role.ASSISTANT, content="The answer is 42."),
        cost_usd=0.001,
        model="mock",
        finish_reason="stop",
    ))

    result = await my_agent(gateway=mock)

    assert mock.invoke_llm_call_count == 1
    assert mock.total_messages_sent == 1
```

## Providers

| Provider | DirectGateway | ControlPlaneGateway |
|---|---|---|
| OpenAI (gpt-4o, gpt-4o-mini, …) | ✓ | ✓ (via control plane) |
| Anthropic (claude-3-5-sonnet, …) | ✓ | ✓ (via control plane) |
| OpenAI-compatible (Ollama, Groq, …) | ✓ | Roadmap |

## Error handling

```python
from sandcastle.exceptions import CostCapExceededError, RateLimitError, SandcastleError

try:
    response = await gateway.invoke_llm(new_messages=[...])
except CostCapExceededError as e:
    print(f"Cost cap of ${e.cap_usd} reached. Spent: ${e.consumed_usd}")
except RateLimitError as e:
    await asyncio.sleep(e.retry_after_seconds)
except SandcastleError:
    raise
```

## Architecture

```
┌─────────────────────────────────────┐
│            Your Agent Code          │
│   (depends only on AgentGateway)    │
└──────────────┬──────────────────────┘
               │
    ┌──────────▼──────────┐
    │    AgentGateway      │  ← Protocol (interface)
    │      Protocol        │
    └──────┬────────┬──────┘
           │        │
  ┌────────▼─┐  ┌───▼──────────────┐
  │  Direct  │  │  ControlPlane    │
  │ Gateway  │  │    Gateway       │
  │          │  │                  │
  │ Local /  │  │   Production     │
  │  Evals   │  │  (zero secrets)  │
  └──────────┘  └────────┬─────────┘
                         │ HTTP
                ┌────────▼─────────┐
                │  Sandcastle      │
                │  Control Plane   │
                │  (holds creds)   │
                └──────────────────┘
```

## Roadmap

- [ ] LangChain adapter (`SandcastleChatModel`)
- [ ] LlamaIndex adapter (`SandcastleLLM`)
- [ ] Streaming support (`invoke_llm_stream`)
- [ ] CrewAI integration
- [ ] Pluggable inference backends (distributed compute)
- [ ] `sandcastle-cli` for one-command control plane deployment

## License

MIT © [Gold Okpa](https://github.com/Goldokpa/Sandcastle)
