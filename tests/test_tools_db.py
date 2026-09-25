"""Tool tests against a real Odoo database with the `ai` views installed (the demo stack).

Skipped automatically when the database is not reachable. Data is discovered from the DB,
so nothing here depends on specific ids or amounts.
"""
import json

import psycopg
import pytest

from api.auth import UserContext
from api.config import settings
from api.tools import run_tool
from api.tools.base import query


def _db_up() -> bool:
    try:
        with psycopg.connect(settings.odoo_db_dsn, connect_timeout=2) as conn:
            conn.execute("SELECT 1 FROM ai.leave_balance LIMIT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_up(), reason="Odoo database with the ai views is not reachable")

ALL_COMPANIES = list(range(1, 50))
HR = frozenset({"hr_holidays.group_hr_holidays_manager"})
SALES = frozenset({"sales_team.group_sale_manager"})
FINANCE = frozenset({"account.group_account_manager"})


def call(name, args, ctx):
    return json.loads(run_tool(name, args, ctx))


@pytest.fixture(scope="module")
def employees():
    # DISTINCT: one employee can hold several leave types, and the tests need two different people.
    rows = query("SELECT DISTINCT employee_id FROM ai.leave_balance WHERE allocated > 0 ORDER BY employee_id LIMIT 2")
    if len(rows) < 2:
        pytest.skip("demo data has fewer than two employees with a leave balance")
    return [r["employee_id"] for r in rows]


def as_employee(emp, groups=frozenset()):
    return UserContext(uid=1000 + emp, employee_id=emp, company_ids=ALL_COMPANIES, groups=groups)


def test_balance_is_internally_consistent(employees):
    rows = call("get_leave_balance", {}, as_employee(employees[0]))["balances"]
    assert rows
    for r in rows:
        assert r["remaining"] == pytest.approx(r["allocated"] - r["taken"], abs=0.011)


def test_plain_user_is_pinned_to_their_own_employee(employees):
    a, b = employees
    own = call("get_leave_balance", {}, as_employee(a))
    assert own["employee_id"] == a
    assert "permission denied" in call("get_leave_balance", {"employee_id": b}, as_employee(a))["error"]


def test_hr_manager_can_read_another_employee(employees):
    a, b = employees
    r = call("get_leave_balance", {"employee_id": b}, as_employee(a, HR))
    assert r["employee_id"] == b and r["balances"]


def test_list_leaves_returns_a_list_for_any_year(employees):
    r = call("list_leaves", {"year": 2000}, as_employee(employees[0]))
    assert r["leaves"] == [] and r["year"] == 2000


def test_company_scope_is_enforced():
    ctx = UserContext(uid=4, employee_id=None, company_ids=[], groups=FINANCE | SALES)
    assert call("overdue_invoices", {}, ctx) == {"totals": [], "top_overdue": []}
    assert call("sales_summary", {"date_from": "2000-01-01", "date_to": "2100-01-01"}, ctx)["summary"] == []


def test_authorised_tools_return_well_formed_data():
    ctx = UserContext(uid=5, employee_id=None, company_ids=ALL_COMPANIES, groups=SALES | FINANCE)
    sales = call("sales_summary", {"date_from": "2000-01-01", "date_to": "2100-01-01"}, ctx)
    assert "error" not in sales and isinstance(sales["summary"], list)
    assert all({"currency", "state", "orders", "total"} <= r.keys() for r in sales["summary"])
    assert "error" not in call("overdue_invoices", {}, ctx)
    assert isinstance(call("invoice_status", {"text": "a"}, ctx)["invoices"], list)


def test_amounts_come_back_as_numbers():
    ctx = UserContext(uid=5, employee_id=None, company_ids=ALL_COMPANIES, groups=SALES)
    rows = call("sales_summary", {"date_from": "2000-01-01", "date_to": "2100-01-01"}, ctx)["summary"]
    if not rows:
        pytest.skip("demo data has no sales orders")
    assert all(isinstance(r["total"], int | float) for r in rows)


def test_search_wildcard_typed_by_the_user_matches_nothing():
    ctx = UserContext(uid=5, employee_id=None, company_ids=ALL_COMPANIES, groups=SALES)
    assert call("find_sale_order", {"text": "%"}, ctx)["orders"] == []


def test_readonly_role_cannot_see_base_tables_or_write():
    with psycopg.connect(settings.odoo_db_dsn) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("SELECT * FROM hr_employee LIMIT 1")
    with psycopg.connect(settings.odoo_db_dsn) as conn, pytest.raises(psycopg.errors.Error):
        conn.execute("DELETE FROM ai.leaves")
