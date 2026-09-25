"""Permission and safety behaviour of the tools. None of these tests needs a database:
every denial happens before any SQL is executed."""
import json
from decimal import Decimal

import pytest

from api.auth import UserContext
from api.tools import REGISTRY, run_tool
from api.tools.base import _json_default, like

PLAIN = UserContext(uid=1, employee_id=10, company_ids=[1], groups=frozenset())
NO_EMPLOYEE = UserContext(uid=2, employee_id=None, company_ids=[1], groups=frozenset())


def call(name, args, ctx):
    return json.loads(run_tool(name, args, ctx))


@pytest.mark.parametrize("name,args", [
    ("sales_summary", {"date_from": "2026-01-01", "date_to": "2026-12-31"}),
    ("find_sale_order", {"text": "S0"}),
    ("invoice_status", {"text": "INV"}),
    ("overdue_invoices", {}),
])
def test_group_protected_tools_deny_plain_user(name, args):
    assert "permission denied" in call(name, args, PLAIN)["error"]


def test_plain_user_cannot_read_another_employees_leave():
    r = call("get_leave_balance", {"employee_id": 99}, PLAIN)
    assert "permission denied" in r["error"] and "own leave" in r["error"]


def test_user_without_employee_is_rejected():
    assert "not linked to an employee" in call("get_leave_balance", {}, NO_EMPLOYEE)["error"]


def test_unknown_tool_returns_error_not_exception():
    assert "unknown tool" in call("drop_database", {}, PLAIN)["error"]


def test_all_tools_are_registered():
    assert set(REGISTRY) == {"get_leave_balance", "list_leaves", "sales_summary",
                             "find_sale_order", "invoice_status", "overdue_invoices",
                             "search_documents"}


def test_every_tool_has_a_description_and_json_schema():
    for t in REGISTRY.values():
        assert len(t.description) > 30 and t.parameters["type"] == "object", t.name


def test_business_tools_are_group_protected_but_leave_and_docs_are_open():
    assert REGISTRY["sales_summary"].groups and REGISTRY["overdue_invoices"].groups
    assert REGISTRY["get_leave_balance"].groups is None  # scoped to the caller instead
    assert REGISTRY["search_documents"].groups is None


def test_like_escapes_wildcards_typed_by_the_user():
    assert like("50%_off") == "%50\\%\\_off%"
    assert like("a\\b") == "%a\\\\b%"


def test_decimals_are_serialised_as_numbers_not_strings():
    assert json.dumps({"x": Decimal("12.50")}, default=_json_default) == '{"x": 12.5}'
