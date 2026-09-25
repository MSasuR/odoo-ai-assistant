"""Usage log WITHOUT personal data: questions and answers are never stored, only metrics.

It feeds the usage figures (questions per day, per category) and the cost estimate.
The user id is stored as a salted hash; it cannot be reversed without the secret.
"""
import hashlib
import json
import logging

from api.config import settings
from api.rag.store import connect

log = logging.getLogger("usage")

# USD per 1M tokens (input, output) per model. ESTIMATE: check against the provider's current price list.
PRICING = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
}

CATEGORY_BY_TOOL = {
    "get_leave_balance": "hr", "list_leaves": "hr",
    "sales_summary": "sales", "find_sale_order": "sales",
    "invoice_status": "invoices", "overdue_invoices": "invoices",
    "search_documents": "documents",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_log (
    id            BIGSERIAL PRIMARY KEY,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_hash     TEXT NOT NULL,
    conversation  TEXT NOT NULL,
    provider      TEXT NOT NULL,
    category      TEXT NOT NULL,
    tools         TEXT[] NOT NULL,
    iterations    INT NOT NULL,
    latency_ms    INT NOT NULL,
    input_tokens  INT NOT NULL,
    output_tokens INT NOT NULL,
    cost_usd      NUMERIC(10, 6) NOT NULL,
    status        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS usage_log_ts_idx ON usage_log (ts);
"""


def user_hash(uid: int) -> str:
    return hashlib.sha256(f"{uid}:{settings.hmac_secret}".encode()).hexdigest()[:12]


def category(tools: list[str]) -> str:
    cats = {CATEGORY_BY_TOOL.get(t, "other") for t in tools}
    if not cats:
        return "no_tools"
    return cats.pop() if len(cats) == 1 else "mixed"


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """model_id: "provider:model" (e.g. "gemini:gemini-2.5-flash-lite"). Unpriced model -> 0."""
    pin, pout = PRICING.get(model_id.split(":")[-1], (0.0, 0.0))
    return round((input_tokens * pin + output_tokens * pout) / 1_000_000, 6)


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)


def record(*, uid: int, conversation: str, provider: str, tools: list[str], iterations: int,
           latency_ms: int, input_tokens: int, output_tokens: int, status: str) -> None:
    """Write the structured log line and the usage row. It must never break the user's response."""
    row = {
        "user_hash": user_hash(uid), "conversation": conversation, "provider": provider,
        "category": category(tools), "tools": tools, "iterations": iterations,
        "latency_ms": latency_ms, "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cost_usd": estimate_cost(provider, input_tokens, output_tokens), "status": status,
    }
    log.info(json.dumps(row))
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO usage_log (user_hash, conversation, provider, category, tools, iterations, "
                "latency_ms, input_tokens, output_tokens, cost_usd, status) VALUES "
                "(%(user_hash)s, %(conversation)s, %(provider)s, %(category)s, %(tools)s, %(iterations)s, "
                "%(latency_ms)s, %(input_tokens)s, %(output_tokens)s, %(cost_usd)s, %(status)s)", row)
    except Exception:  # noqa: BLE001 - logging is best-effort
        log.warning("could not write usage_log", exc_info=True)
