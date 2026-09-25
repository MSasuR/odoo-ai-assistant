from api.auth import UserContext
from api.config import csv_set, settings
from api.tools.base import MAX_ROWS, like, query, tool

INVOICE_GROUPS = csv_set(settings.invoice_groups)

PAYMENT_STATES = "paid=paid, not_paid=unpaid, partial=partially paid"


@tool(
    "invoice_status",
    "Status of one or more invoices by number or customer/vendor name: date, due date, "
    f"amount and outstanding balance. Payment states: {PAYMENT_STATES}.",
    {"type": "object", "properties": {
        "text": {"type": "string", "description": "Invoice number or part of the customer/vendor name"},
        "move_type": {"type": "string", "enum": ["out_invoice", "in_invoice"],
                      "description": "out_invoice=customer invoice (sales), "
                                     "in_invoice=vendor bill (purchases). Optional."}},
     "required": ["text"]},
    groups=INVOICE_GROUPS,
)
def invoice_status(ctx: UserContext, args: dict) -> dict:
    p = like(args["text"])
    sql = ("SELECT name, company, partner, move_type, invoice_date, due_date, payment_state, "
           "amount_total, amount_residual, currency FROM ai.invoices "
           "WHERE company_id = ANY(%s) AND state = 'posted' AND (name ILIKE %s OR partner ILIKE %s) ")
    params: list = [ctx.company_ids, p, p]
    if args.get("move_type") in ("out_invoice", "in_invoice"):
        sql += "AND move_type = %s "
        params.append(args["move_type"])
    return {"invoices": query(sql + "ORDER BY invoice_date DESC LIMIT %s", params + [MAX_ROWS])}


@tool(
    "overdue_invoices",
    "Customer invoices that are past due and still have an outstanding balance (collections), "
    "largest balance first. Includes the total outstanding per currency.",
    {"type": "object", "properties": {
        "company": {"type": "string", "description": "Optional. Company name (partial match)."}}},
    groups=INVOICE_GROUPS,
)
def overdue_invoices(ctx: UserContext, args: dict) -> dict:
    where = ("company_id = ANY(%s) AND move_type = 'out_invoice' AND state = 'posted' "
             "AND payment_state IN ('not_paid', 'partial') AND due_date < CURRENT_DATE ")
    params: list = [ctx.company_ids]
    if args.get("company"):
        where += "AND company ILIKE %s "
        params.append(like(args["company"]))
    totals = query(f"SELECT currency, COUNT(*) AS invoices, SUM(amount_residual) AS pending "
                   f"FROM ai.invoices WHERE {where} GROUP BY currency", params)
    top = query(f"SELECT name, company, partner, due_date, amount_residual, currency "
                f"FROM ai.invoices WHERE {where} ORDER BY amount_residual DESC LIMIT %s", params + [MAX_ROWS])
    return {"totals": totals, "top_overdue": top}
