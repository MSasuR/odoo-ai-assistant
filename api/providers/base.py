"""Common interface for LLM providers.

Neutral message format (dicts) that each provider translates to its own:
  {"role": "user", "content": str}
  {"role": "assistant", "content": str, "tool_calls": [ToolCall...], "_raw": <opaque>}
  {"role": "tool", "name": str, "tool_call_id": str, "content": str(json)}
`_raw` keeps the provider's original message (Gemini needs it to preserve reasoning
signatures across tool-calling turns).

Neutral tool schema: {"name", "description", "parameters": <JSON Schema>}.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str = ""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    raw: object = None


class Provider(ABC):
    name: str

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse: ...

    @abstractmethod
    def embed(self, texts: list[str], kind: str = "document") -> list[list[float]]:
        """kind: "document" (ingestion) or "query" (search); some models optimise each differently."""
        ...
