"""The Odoo module signs with its own lib (standard library only); the API verifies with
api.auth. This test guarantees both formats stay compatible."""
import importlib.util
from pathlib import Path

import pytest

from api.auth import AuthError, verify_token

LIB = Path(__file__).parents[1] / "odoo_addon" / "ai_assistant_chat" / "lib.py"
pytestmark = pytest.mark.skipif(not LIB.exists(), reason="odoo_addon not available")

SECRET = "test-secret"
IDENTITY = {"uid": 12, "employee_id": 34, "company_ids": [1, 5],
            "groups": ["base.group_user", "sales_team.group_sale_salesman"]}


@pytest.fixture(scope="module")
def odoo_lib():
    spec = importlib.util.spec_from_file_location("odoo_ai_lib", LIB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_api_accepts_token_signed_by_odoo(odoo_lib):
    ctx = verify_token(odoo_lib.sign_token(IDENTITY, SECRET), SECRET)
    assert ctx.uid == 12 and ctx.employee_id == 34 and ctx.company_ids == [1, 5]
    assert ctx.in_any_group({"sales_team.group_sale_salesman"})


def test_wrong_secret_is_rejected(odoo_lib):
    with pytest.raises(AuthError):
        verify_token(odoo_lib.sign_token(IDENTITY, "other"), SECRET)


def test_expired_token_from_odoo_is_rejected(odoo_lib):
    with pytest.raises(AuthError, match="expired"):
        verify_token(odoo_lib.sign_token(IDENTITY, SECRET, ttl=-1), SECRET)


def test_employee_can_be_null(odoo_lib):
    ctx = verify_token(odoo_lib.sign_token({**IDENTITY, "employee_id": None}, SECRET), SECRET)
    assert ctx.employee_id is None
