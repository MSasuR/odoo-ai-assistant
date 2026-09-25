import logging
import re
import time

from google import genai
from google.genai import errors, types

from api.providers.base import LLMResponse, Provider, ToolCall, Usage

# pgvector HNSW supports up to 2000 dimensions; gemini-embedding-001 returns 3072 by default.
EMBED_DIM = 768
RETRIES = 4  # total attempts on 429/5xx (transient API overload)
MAX_WAIT = 30  # seconds: if Google asks for a longer wait (daily quota) we do not block the request
_RETRY_IN = re.compile(r"retry in ([\d.]+)s", re.I)

log = logging.getLogger(__name__)


def _with_retry(fn):
    for attempt in range(RETRIES):
        try:
            return fn()
        except (errors.ServerError, errors.ClientError) as e:
            transient = isinstance(e, errors.ServerError) or getattr(e, "code", 0) == 429
            if not transient or attempt == RETRIES - 1:
                raise
            if "PerDay" in str(e):  # daily quota exhausted: waiting a few seconds is pointless
                log.error("Gemini: daily quota exhausted (%s)", getattr(e, "code", ""))
                raise
            delay = 2 ** attempt  # 1s, 2s, 4s
            hint = _RETRY_IN.search(str(e))
            if hint:  # Google states how long to wait on quota 429s
                delay = float(hint.group(1)) + 1
                if delay > MAX_WAIT:
                    raise
            log.warning("Gemini %s, retry %d/%d in %.0fs", e.code, attempt + 1, RETRIES - 1, delay)
            time.sleep(delay)


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, embed_model: str = "gemini-embedding-001"):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.embed_model = embed_model

    @staticmethod
    def _to_contents(messages: list[dict]) -> list[types.Content]:
        contents: list[types.Content] = []
        for m in messages:
            role = m["role"]
            if role == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=m["content"])]))
            elif role == "assistant":
                if m.get("_raw") is not None:
                    contents.append(m["_raw"])
                    continue
                parts = [types.Part(text=m["content"])] if m.get("content") else []
                parts += [
                    types.Part(function_call=types.FunctionCall(name=c.name, args=c.args))
                    for c in m.get("tool_calls", [])
                ]
                contents.append(types.Content(role="model", parts=parts))
            elif role == "tool":
                part = types.Part.from_function_response(
                    name=m["name"], response={"result": m["content"]}
                )
                # Gemini requires all responses of one turn inside a single Content.
                if contents and contents[-1].role == "user" and contents[-1].parts and \
                        contents[-1].parts[0].function_response is not None:
                    contents[-1].parts.append(part)
                else:
                    contents.append(types.Content(role="user", parts=[part]))
        return contents

    @staticmethod
    def _to_tools(tools: list[dict] | None) -> list[types.Tool] | None:
        if not tools:
            return None
        decls = []
        for t in tools:
            params = t.get("parameters")
            if params and not params.get("properties"):
                params = None  # Gemini rejects objects without properties
            decls.append(
                types.FunctionDeclaration(
                    name=t["name"], description=t["description"], parameters=params
                )
            )
        return [types.Tool(function_declarations=decls)]

    def chat(self, messages, tools=None, system=None, temperature=0.2) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            tools=self._to_tools(tools),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True, maximum_remote_calls=None),
        )
        contents = self._to_contents(messages)
        r = _with_retry(lambda: self.client.models.generate_content(
            model=self.model, contents=contents, config=config))
        calls = [
            ToolCall(name=c.name, args=dict(c.args or {}), id=c.id or "")
            for c in (r.function_calls or [])
        ]
        text = "".join(
            p.text for p in (r.candidates[0].content.parts or []) if p.text and not p.thought
        ) if r.candidates and r.candidates[0].content else ""
        u = r.usage_metadata
        return LLMResponse(
            text=text,
            tool_calls=calls,
            usage=Usage(
                input_tokens=(u.prompt_token_count or 0) if u else 0,
                output_tokens=(u.candidates_token_count or 0) if u else 0,
            ),
            raw=r.candidates[0].content if r.candidates else None,
        )

    def embed(self, texts: list[str], kind: str = "document") -> list[list[float]]:
        task = "RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
        out: list[list[float]] = []
        for i in range(0, len(texts), 100):  # API batch limit
            batch = texts[i : i + 100]
            r = _with_retry(lambda batch=batch: self.client.models.embed_content(
                model=self.embed_model,
                contents=batch,
                config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM, task_type=task),
            ))
            out += [e.values for e in r.embeddings]
        return out
