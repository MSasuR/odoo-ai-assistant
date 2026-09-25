import pytest

from api.auth import AuthError, sign_token, verify_token

SECRET = "test-secret"
PAYLOAD = {"uid": 7, "employee_id": 42, "company_ids": [1, 5], "groups": ["sales_team.group_sale_salesman"]}


def test_roundtrip():
    ctx = verify_token(sign_token(PAYLOAD, SECRET), SECRET)
    assert ctx.uid == 7 and ctx.employee_id == 42 and ctx.company_ids == [1, 5]
    assert ctx.in_any_group({"sales_team.group_sale_salesman"})
    assert not ctx.in_any_group({"account.group_account_manager"})


def test_tampered_payload_rejected():
    body, sig = sign_token(PAYLOAD, SECRET).split(".")
    forged = sign_token({**PAYLOAD, "uid": 1}, "other-secret").split(".")[0]
    with pytest.raises(AuthError):
        verify_token(f"{forged}.{sig}", SECRET)


def test_wrong_secret_rejected():
    with pytest.raises(AuthError):
        verify_token(sign_token(PAYLOAD, "attacker"), SECRET)


def test_expired_rejected():
    with pytest.raises(AuthError, match="expired"):
        verify_token(sign_token(PAYLOAD, SECRET, ttl=-1), SECRET)


@pytest.mark.parametrize("junk", ["", "abc", "a.b.c", "!!!.???"])
def test_malformed_rejected(junk):
    with pytest.raises(AuthError):
        verify_token(junk, SECRET)
