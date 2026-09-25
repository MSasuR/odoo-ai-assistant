import pytest
from google.genai import errors

from api.providers import gemini


class _Boom(errors.ServerError):
    def __init__(self, code=503):
        self.code = code


class _Quota(errors.ClientError):
    def __init__(self, msg):
        self.code = 429
        self._msg = msg

    def __str__(self):
        return self._msg


def test_retries_transient_then_succeeds(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _Boom(503)
        return "ok"

    assert gemini._with_retry(flaky) == "ok" and calls["n"] == 3


def test_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def always():
        calls["n"] += 1
        raise _Boom(503)

    with pytest.raises(errors.ServerError):
        gemini._with_retry(always)
    assert calls["n"] == gemini.RETRIES


def test_429_honours_retry_hint(monkeypatch):
    slept = []
    monkeypatch.setattr(gemini.time, "sleep", slept.append)
    calls = {"n": 0}

    def quota_then_ok():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _Quota("quota. Please retry in 19.4s.")
        return "ok"

    assert gemini._with_retry(quota_then_ok) == "ok"
    assert slept == [pytest.approx(20.4)]


def test_429_with_long_wait_fails_fast(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda s: pytest.fail("must not sleep"))
    with pytest.raises(errors.ClientError):
        gemini._with_retry(lambda: (_ for _ in ()).throw(_Quota("Please retry in 3600s")))


def test_non_transient_client_error_is_not_retried(monkeypatch):
    class _Bad(errors.ClientError):
        def __init__(self):
            self.code = 400
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise _Bad()

    with pytest.raises(errors.ClientError):
        gemini._with_retry(bad)
    assert calls["n"] == 1


def test_daily_quota_is_not_retried(monkeypatch):
    monkeypatch.setattr(gemini.time, "sleep", lambda s: pytest.fail("must not sleep"))
    calls = {"n": 0}

    def daily():
        calls["n"] += 1
        raise _Quota("quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier. Please retry in 5s")

    with pytest.raises(errors.ClientError):
        gemini._with_retry(daily)
    assert calls["n"] == 1
