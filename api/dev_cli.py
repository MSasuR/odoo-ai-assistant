"""Console chat to try the assistant without the Odoo module (development only).

It signs a token for the chosen role and talks to POST /chat, exactly as Odoo does.

    docker compose exec assistant python -m api.dev_cli --role user
    docker compose exec assistant python -m api.dev_cli --role finance --ask "How much is overdue?"

The employee and companies are discovered from the `ai` views unless given explicitly.
"""
import argparse
import time

import httpx

from api.auth import sign_token
from api.tools.base import query

ROLES = {
    "user": [],  # regular employee, no special groups
    "hr": ["hr_holidays.group_hr_holidays_manager"],
    "sales": ["sales_team.group_sale_manager"],
    "finance": ["account.group_account_manager"],
    "admin": ["hr_holidays.group_hr_holidays_manager", "sales_team.group_sale_manager",
              "account.group_account_manager"],
}


def discover_employee() -> int:
    rows = query("SELECT employee_id FROM ai.leave_balance ORDER BY remaining DESC LIMIT 1")
    if not rows:
        raise SystemExit("No employee with a leave balance found; pass --employee explicitly.")
    return rows[0]["employee_id"]


def discover_companies() -> list[int]:
    rows = query("SELECT company_id FROM ai.employees UNION SELECT company_id FROM ai.sales_orders "
                 "UNION SELECT company_id FROM ai.invoices")
    return sorted(r["company_id"] for r in rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=ROLES, default="user")
    ap.add_argument("--employee", type=int, help="hr.employee id (default: discovered)")
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--ask", help="ask a single question and exit")
    a = ap.parse_args()

    employee = a.employee or discover_employee()
    companies = discover_companies()
    payload = {"uid": 900000 + employee, "employee_id": employee,
               "company_ids": companies, "groups": ROLES[a.role]}
    client = httpx.Client(base_url=a.url, timeout=120)
    cid = None
    print(f"role={a.role} employee_id={employee} companies={companies}  (Ctrl+C to quit)")

    def ask(msg: str) -> None:
        nonlocal cid
        headers = {"Authorization": "Bearer " + sign_token(payload, ttl=600)}
        body = {"message": msg, **({"conversation_id": cid} if cid else {})}
        t = time.perf_counter()
        r = client.post("/chat", json=body, headers=headers)
        if r.status_code != 200:
            print(f"  [HTTP {r.status_code}] {r.json().get('detail', r.text)}")
            return
        d = r.json()
        cid = d["conversation_id"]
        print(f"\n{d['answer']}")
        if d["sources"]:
            print("  sources:", "; ".join(f"{s['source']} · {s['section']}" for s in d["sources"]))
        print(f"  [{time.perf_counter() - t:.1f}s · tools: {d['tools_used'] or '-'}]\n")

    if a.ask:
        return ask(a.ask)
    while True:
        try:
            msg = input("you> ").strip()
        except (KeyboardInterrupt, EOFError):
            return print()
        if msg:
            ask(msg)


if __name__ == "__main__":
    main()
