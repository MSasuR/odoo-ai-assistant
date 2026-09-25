"""Tool registry + read-only DB access + group-based permission checks.

Tools run fixed, parameterised SQL over the views of the `ai` schema (role
`ai_readonly`). The LLM only picks the tool and its arguments; it never writes SQL.
"""
import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from api.auth import UserContext
from api.config import settings

MAX_ROWS = 20


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable[[UserContext, dict], dict]
    groups: set[str] | None = None  # None = any authenticated user


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, parameters: dict | None = None, groups: set[str] | None = None):
    def deco(fn):
        REGISTRY[name] = Tool(
            name, description, parameters or {"type": "object", "properties": {}}, fn, groups
        )
        return fn
    return deco


def query(sql: str, params: tuple | list = ()) -> list[dict]:
    with psycopg.connect(settings.odoo_db_dsn, row_factory=dict_row, connect_timeout=5) as conn:
        return conn.execute(sql, params).fetchall()


def like(text: str) -> str:
    """Safe ILIKE pattern: escapes wildcards typed by the user."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _json_default(o):
    # Decimal -> number (not string), so the LLM does not receive amounts as text.
    if isinstance(o, Decimal):
        return float(o)
    return str(o)  # dates and the rest -> ISO / text


def schemas() -> list[dict]:
    return [{"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in REGISTRY.values()]


def run_tool(name: str, args: dict, ctx: UserContext) -> str:
    """Run a tool and return a JSON string. Errors come back as {"error": ...} so the LLM
    can explain them to the user instead of breaking the loop."""
    t = REGISTRY.get(name)
    if t is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    if t.groups is not None and not ctx.in_any_group(t.groups):
        return json.dumps({"error": "permission denied: this user has no access to this information"})
    try:
        return json.dumps(t.fn(ctx, args or {}), default=_json_default, ensure_ascii=False)
    except PermissionError as e:  # business rule inside a tool (e.g. someone else's leave)
        return json.dumps({"error": f"permission denied: {e}"})
    except Exception as e:  # noqa: BLE001 - reported to the LLM, not propagated
        return json.dumps({"error": f"failed to run {name}: {type(e).__name__}"})
