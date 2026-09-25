from api.providers.base import LLMResponse, Provider, ToolCall, Usage


class FakeProvider(Provider):
    """Scripted provider: returns the responses in order and records what it received."""
    name = "fake"

    def __init__(self, script: list[LLMResponse]):
        self.script = list(script)
        self.calls: list[dict] = []

    def chat(self, messages, tools=None, system=None, temperature=0.2):
        self.calls.append({"messages": list(messages), "system": system, "tools": tools})
        return self.script.pop(0) if self.script else LLMResponse(text="(end)")

    def embed(self, texts, kind="document"):
        return [[0.0] * 768 for _ in texts]


def say(text: str, tokens=(10, 5)) -> LLMResponse:
    return LLMResponse(text=text, usage=Usage(*tokens))


def call(name: str, args: dict | None = None, tokens=(10, 5)) -> LLMResponse:
    return LLMResponse(text="", tool_calls=[ToolCall(name=name, args=args or {}, id=f"id-{name}")],
                       usage=Usage(*tokens))
