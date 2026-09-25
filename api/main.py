import logging
import time
import uuid
from contextlib import asynccontextmanager

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from api import usage
from api.agent import run_agent
from api.auth import AuthError, UserContext, verify_token
from api.config import settings
from api.conversations import store as conversations
from api.providers import get_provider
from api.providers.base import Provider
from api.ratelimit import limiter

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("chat")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        usage.ensure_schema()
    except Exception:  # noqa: BLE001 - the API must start even if the usage log cannot
        log.warning("usage_log unavailable at startup", exc_info=True)
    yield


app = FastAPI(title="Odoo AI Assistant", lifespan=lifespan)


def provider_dep() -> Provider:
    return get_provider()


def current_user(authorization: str | None = Header(default=None)) -> UserContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing token")
    try:
        return verify_token(authorization[7:].strip())
    except AuthError as e:
        raise HTTPException(401, f"invalid token: {e}") from e


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=64, pattern=r"^[\w-]+$")


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    tools_used: list[str]
    sources: list[dict]


def _ping(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute("select 1")
        return True
    except Exception:  # noqa: BLE001
        return False


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "odoo_db": _ping(settings.odoo_db_dsn),
        "vector_db": _ping(settings.vector_db_dsn),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, ctx: UserContext = Depends(current_user),
         provider: Provider = Depends(provider_dep)):
    if not limiter.allow(ctx.uid):
        raise HTTPException(429, "too many requests, please wait a moment")

    cid = req.conversation_id or uuid.uuid4().hex
    label = f"{provider.name}:{getattr(provider, 'model', '')}"  # e.g. gemini:gemini-2.5-flash-lite
    started = time.perf_counter()
    try:
        result = run_agent(provider, ctx, conversations.get(ctx.uid, cid), req.message)
    except Exception as e:  # noqa: BLE001 - provider down, quota exhausted, etc.
        usage.record(uid=ctx.uid, conversation=cid, provider=label, tools=[], iterations=0,
                     latency_ms=int((time.perf_counter() - started) * 1000), input_tokens=0,
                     output_tokens=0, status=f"error:{type(e).__name__}")
        raise HTTPException(503, "The assistant is not available right now, please try again.") from e

    conversations.append(ctx.uid, cid, req.message, result.answer)
    usage.record(uid=ctx.uid, conversation=cid, provider=label, tools=result.tools_used,
                 iterations=result.iterations, latency_ms=int((time.perf_counter() - started) * 1000),
                 input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens,
                 status=result.stopped)
    return ChatResponse(answer=result.answer, conversation_id=cid,
                        tools_used=result.tools_used, sources=result.sources)
