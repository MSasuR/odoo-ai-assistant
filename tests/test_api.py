import pytest
from fastapi.testclient import TestClient

from api import main
from api.auth import sign_token
from api.conversations import ConversationStore
from api.ratelimit import RateLimiter
from tests.fakes import FakeProvider, say


@pytest.fixture
def client(monkeypatch):
    fake = FakeProvider([say("answer 1"), say("answer 2"), say("answer 3")])
    main.app.dependency_overrides[main.provider_dep] = lambda: fake
    monkeypatch.setattr(main.usage, "record", lambda **kw: None)  # do not write to usage_log
    monkeypatch.setattr(main, "conversations", ConversationStore())
    monkeypatch.setattr(main, "limiter", RateLimiter(limit=3))
    c = TestClient(main.app)
    c.fake = fake
    yield c
    main.app.dependency_overrides.clear()


def auth(uid=1, **extra):
    return {"Authorization": "Bearer " + sign_token({"uid": uid, "employee_id": 5, "company_ids": [1],
                                                     "groups": [], **extra})}


def test_no_token_is_401(client):
    assert client.post("/chat", json={"message": "hello"}).status_code == 401


def test_forged_token_is_401(client):
    bad = {"Authorization": "Bearer " + sign_token({"uid": 1}, secret="other")}
    assert client.post("/chat", json={"message": "hello"}, headers=bad).status_code == 401


def test_expired_token_is_401(client):
    h = {"Authorization": "Bearer " + sign_token({"uid": 1}, ttl=-5)}
    assert client.post("/chat", json={"message": "hello"}, headers=h).status_code == 401


def test_chat_ok_returns_conversation_id(client):
    r = client.post("/chat", json={"message": "hello"}, headers=auth())
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "answer 1" and body["conversation_id"] and body["tools_used"] == []


def test_conversation_continues_with_history(client):
    cid = client.post("/chat", json={"message": "one"}, headers=auth()).json()["conversation_id"]
    client.post("/chat", json={"message": "two", "conversation_id": cid}, headers=auth())
    sent = [m["content"] for m in client.fake.calls[1]["messages"]]
    assert sent == ["one", "answer 1", "two"]


def test_conversations_are_isolated_between_users(client):
    cid = client.post("/chat", json={"message": "A's secret"}, headers=auth(uid=1)).json()["conversation_id"]
    client.post("/chat", json={"message": "hello", "conversation_id": cid}, headers=auth(uid=2))
    assert [m["content"] for m in client.fake.calls[1]["messages"]] == ["hello"]  # B never sees A's turns


@pytest.mark.parametrize("body", [{"message": ""}, {"message": "x" * 2001},
                                  {"message": "hello", "conversation_id": "../etc"}])
def test_invalid_input_is_422(client, body):
    assert client.post("/chat", json=body, headers=auth()).status_code == 422


def test_rate_limit_is_per_user(client):
    for _ in range(3):
        assert client.post("/chat", json={"message": "x"}, headers=auth(uid=1)).status_code == 200
    assert client.post("/chat", json={"message": "x"}, headers=auth(uid=1)).status_code == 429
    assert client.post("/chat", json={"message": "x"}, headers=auth(uid=2)).status_code == 200


def test_provider_failure_is_503_without_leaking_details(client):
    def boom(*a, **k):
        raise RuntimeError("invalid key sk-SECRET")
    client.fake.chat = boom
    r = client.post("/chat", json={"message": "hello"}, headers=auth())
    assert r.status_code == 503 and "SECRET" not in r.text


def test_history_store_is_bounded_and_expires():
    t = [0.0]
    s = ConversationStore(ttl=10, max_messages=4, max_conversations=2, clock=lambda: t[0])
    for i in range(5):
        s.append(1, "c", f"u{i}", f"a{i}")
    assert [m["content"] for m in s.get(1, "c")] == ["u3", "a3", "u4", "a4"]
    t[0] = 11
    assert s.get(1, "c") == []
    s.append(1, "a", "x", "y")
    s.append(1, "b", "x", "y")
    s.append(1, "c", "x", "y")
    assert s.get(1, "a") == []  # the oldest conversation is evicted


def test_cost_is_estimated_per_model():
    from api.usage import estimate_cost
    flash = estimate_cost("gemini:gemini-2.5-flash", 1_000_000, 1_000_000)
    lite = estimate_cost("gemini:gemini-2.5-flash-lite", 1_000_000, 1_000_000)
    assert flash == 2.8 and lite == 0.5 and lite < flash
    assert estimate_cost("gemini:unknown-model", 1000, 1000) == 0.0


def test_usage_category_from_tools():
    from api.usage import category
    assert category([]) == "no_tools"
    assert category(["get_leave_balance", "list_leaves"]) == "hr"
    assert category(["sales_summary", "overdue_invoices"]) == "mixed"
    assert category(["search_documents"]) == "documents"


def test_user_hash_is_stable_short_and_depends_on_the_secret(monkeypatch):
    from api import usage
    h = usage.user_hash(42)
    assert h == usage.user_hash(42) and h != usage.user_hash(43) and len(h) == 12
    monkeypatch.setattr(usage.settings, "hmac_secret", "another-secret")
    assert usage.user_hash(42) != h  # not reversible without the secret
