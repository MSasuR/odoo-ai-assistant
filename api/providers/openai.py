import json

from openai import OpenAI

from api.providers.base import LLMResponse, Provider, ToolCall, Usage

EMBED_DIM = 768  # text-embedding-3-small supports `dimensions`; kept equal to Gemini's


class OpenAIProvider(Provider):
    """OpenAI implementation of the provider interface (not covered by live tests yet)."""

    name = "openai"

    def __init__(self, api_key: str, model: str, embed_model: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.embed_model = embed_model

    @staticmethod
    def _to_messages(messages: list[dict], system: str | None) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or None,
                    "tool_calls": [
                        {"id": c.id, "type": "function",
                         "function": {"name": c.name, "arguments": json.dumps(c.args)}}
                        for c in m["tool_calls"]
                    ],
                })
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            else:
                out.append({"role": m["role"], "content": m["content"]})
        return out

    def chat(self, messages, tools=None, system=None, temperature=0.2) -> LLMResponse:
        kwargs = {}
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": {
                    "name": t["name"], "description": t["description"],
                    "parameters": t.get("parameters") or {"type": "object", "properties": {}},
                }} for t in tools
            ]
        r = self.client.chat.completions.create(
            model=self.model, messages=self._to_messages(messages, system),
            temperature=temperature, **kwargs,
        )
        msg = r.choices[0].message
        calls = [
            ToolCall(name=c.function.name, args=json.loads(c.function.arguments or "{}"), id=c.id)
            for c in (msg.tool_calls or [])
        ]
        return LLMResponse(
            text=msg.content or "",
            tool_calls=calls,
            usage=Usage(r.usage.prompt_tokens, r.usage.completion_tokens) if r.usage else Usage(),
            raw=msg,
        )

    def embed(self, texts: list[str], kind: str = "document") -> list[list[float]]:
        r = self.client.embeddings.create(model=self.embed_model, input=texts, dimensions=EMBED_DIM)
        return [d.embedding for d in r.data]
