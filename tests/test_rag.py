"""Retriever tests against real pgvector + Gemini embeddings. Skipped without an API key,
without the vector database, or before the corpus has been ingested."""
import json

import psycopg
import pytest

from api.auth import UserContext
from api.config import settings
from api.tools import run_tool


def _ready() -> bool:
    if not settings.gemini_api_key:
        return False
    try:
        with psycopg.connect(settings.vector_db_dsn, connect_timeout=2) as c:
            return c.execute("select count(*) from chunks").fetchone()[0] > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ready(), reason="no API key, pgvector or ingested corpus")

CTX = UserContext(uid=1, employee_id=None, company_ids=[1], groups=frozenset())


def search(q):
    return json.loads(run_tool("search_documents", {"query": q}, CTX))


def test_relevant_question_returns_a_cited_source():
    r = search("Who approves my time-off request and how long do they have to answer?")
    assert r["results"] and r["results"][0]["source"].endswith("hr/leave-policy.md")
    assert r["results"][0]["section"]


def test_out_of_scope_returns_nothing_and_warns():
    r = search("What is the recipe for chocolate cake?")
    assert r["results"] == [] and "do not invent" in r["note"].lower()
