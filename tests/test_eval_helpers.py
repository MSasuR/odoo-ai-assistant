"""The evaluation harness must be able to FAIL. These tests give it wrong answers on purpose
(negative controls) so a green evaluation means something."""
import pytest

from api import agent
from api.auth import UserContext
from evals import agent_eval
from evals.agent_eval import Case, evaluate, mentions, numbers_in
from tests.fakes import FakeProvider, call, say

CTX = UserContext(uid=1, employee_id=10, company_ids=[1], groups=frozenset())


@pytest.mark.parametrize("text,value,expected", [
    ("You have 15 days left.", 15, True),
    ("You have 15.0 days left.", 15, True),
    ("You have 20 days left.", 15, False),
    ("Total: 1,189,415,614.50 CLP", 1189415614.5, True),
    ("Total: 1.189.415.614,50 CLP", 1189415614.5, True),
    ("You have 8.54 days", 8.54, True),
    ("You have 8.5 days", 8.54, False),
    ("no numbers here", 3, False),
])
def test_number_matching_is_format_tolerant_but_exact(text, value, expected):
    assert mentions(text, value) is expected


def test_numbers_are_extracted_from_mixed_text():
    assert 45.0 in numbers_in("Meals: up to 45 EUR per day, or 60 EUR elsewhere.")


def _case(**kw):
    return Case(id="c", category="hr", question="q", ctx=CTX, **kw)


def test_correct_answer_passes(monkeypatch):
    monkeypatch.setattr(agent, "run_tool", lambda *a: "{}")
    p = FakeProvider([call("get_leave_balance"), say("You have 15 days left.")])
    r = evaluate(_case(expect_tool="get_leave_balance", expect_numbers=[15.0]), p, sleep=0)
    assert r["passed"] is True


def test_wrong_number_fails(monkeypatch):
    monkeypatch.setattr(agent, "run_tool", lambda *a: "{}")
    p = FakeProvider([call("get_leave_balance"), say("You have 3 days left.")])
    r = evaluate(_case(expect_tool="get_leave_balance", expect_numbers=[15.0]), p, sleep=0)
    assert r["passed"] is False and r["checks"]["has 15"] is False


def test_wrong_tool_fails(monkeypatch):
    monkeypatch.setattr(agent, "run_tool", lambda *a: "{}")
    p = FakeProvider([call("list_leaves"), say("You have 15 days left.")])
    r = evaluate(_case(expect_tool="get_leave_balance", expect_numbers=[15.0]), p, sleep=0)
    assert r["passed"] is False and r["checks"]["tool"] is False


def test_leaking_a_protected_number_fails(monkeypatch):
    monkeypatch.setattr(agent, "run_tool", lambda *a: "{}")
    p = FakeProvider([call("get_leave_balance"), say("That employee has 15 days left.")])
    r = evaluate(_case(forbid_numbers=[15.0]), p, sleep=0)
    assert r["passed"] is False


def test_citing_sources_when_none_should_exist_fails(monkeypatch):
    monkeypatch.setattr(agent, "run_tool", lambda *a: '{"results": [{"source": "x.md", "section": "s"}]}')
    p = FakeProvider([call("search_documents"), say("The policy says X.")])
    r = evaluate(_case(expect_no_sources=True), p, sleep=0)
    assert r["passed"] is False


def test_provider_error_is_reported_not_raised():
    class Boom(FakeProvider):
        def chat(self, *a, **k):
            raise RuntimeError("quota")
    r = evaluate(_case(), Boom([]), sleep=0)
    assert r["passed"] is False and r["error"] == "RuntimeError"


def test_summary_counts_and_percentiles():
    results = [
        {"id": "a", "passed": True, "checks": {"tool": True}, "latency_s": 1.0,
         "input_tokens": 10, "output_tokens": 5},
        {"id": "b", "passed": False, "checks": {"tool": False}, "latency_s": 3.0,
         "input_tokens": 20, "output_tokens": 5},
        {"id": "c", "passed": False, "error": "RuntimeError"},
    ]
    s = agent_eval.summarise(results, "gemini:gemini-2.5-flash")
    assert (s["cases"], s["passed"], s["errors"]) == (3, 1, 1)
    assert s["tool_choice_accuracy"] == 0.5 and s["latency_p50_s"] == 2.0
