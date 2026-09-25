from api.auth import UserContext
from api.config import csv_set, settings
from api.tools.base import MAX_ROWS, like, query, tool

SALES_GROUPS = csv_set(settings.sales_groups)


@tool(
    "sales_summary",
    "Summary of sales orders in a date range: order count and total amount per currency and state. "
    "Only companies the user can access. States: sale=confirmed, draft=quotation, cancel=cancelled.",
    {"type": "object", "properties": {
        "date_from": {"type": "string", "description": "YYYY-MM-DD"},
        "date_to": {"type": "string", "description": "YYYY-MM-DD"},
        "company": {"type": "string", "description": "Optional. Company name (partial match)."}},
     "required": ["date_from", "date_to"]},
    groups=SALES_GROUPS,
)
def sales_summary(ctx: UserContext, args: dict) -> dict:
    sql = ("SELECT currency, state, COUNT(*) AS orders, SUM(amount_total) AS total "
           "FROM ai.sales_orders WHERE company_id = ANY(%s) AND order_date BETWEEN %s AND %s ")
    params: list = [ctx.company_ids, args["date_from"], args["date_to"]]
    if args.get("company"):
        sql += "AND company ILIKE %s "
        params.append(like(args["company"]))
    rows = query(sql + "GROUP BY currency, state ORDER BY currency, state", params)
    return {"date_from": args["date_from"], "date_to": args["date_to"], "summary": rows}


@tool(
    "find_sale_order",
    "Find sales orders by number (e.g. S00123) or customer name.",
    {"type": "object", "properties": {
        "text": {"type": "string", "description": "Order number or part of the customer name"}},
     "required": ["text"]},
    groups=SALES_GROUPS,
)
def find_sale_order(ctx: UserContext, args: dict) -> dict:
    p = like(args["text"])
    rows = query(
        "SELECT name, company, customer, order_date, state, amount_total, currency "
        "FROM ai.sales_orders WHERE company_id = ANY(%s) AND (name ILIKE %s OR customer ILIKE %s) "
        "ORDER BY order_date DESC LIMIT %s", (ctx.company_ids, p, p, MAX_ROWS))
    return {"orders": rows}
