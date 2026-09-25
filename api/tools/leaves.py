from api.auth import UserContext
from api.config import csv_set, settings
from api.tools.base import MAX_ROWS, query, tool

# Groups allowed to look at OTHER employees' leave (approvers / HR).
HR_VIEWERS = csv_set(settings.hr_viewer_groups)


def _target_employee(ctx: UserContext, args: dict) -> int:
    """Employee to query: the caller's own, or the requested one if the caller is HR/approver."""
    requested = args.get("employee_id")
    if requested and requested != ctx.employee_id:
        if not ctx.in_any_group(HR_VIEWERS):
            raise PermissionError("you can only query your own leave")
        return int(requested)
    if not ctx.employee_id:
        raise PermissionError("your user is not linked to an employee")
    return ctx.employee_id


@tool(
    "get_leave_balance",
    "Leave balance (allocated, taken and remaining days) per leave type, e.g. annual leave. "
    "Defaults to the current user; an approver/HR user may pass employee_id.",
    {"type": "object", "properties": {
        "employee_id": {"type": "integer", "description": "Optional. Approvers/HR only."}}},
)
def get_leave_balance(ctx: UserContext, args: dict) -> dict:
    emp = _target_employee(ctx, args)
    rows = query(
        "SELECT leave_type, allocated, taken, remaining FROM ai.leave_balance "
        "WHERE employee_id = %s ORDER BY leave_type", (emp,))
    return {"employee_id": emp, "balances": rows}


@tool(
    "list_leaves",
    "List the leave requests of a given year (dates, days, state). "
    "States: validate=approved, confirm=pending approval, refuse=refused.",
    {"type": "object", "properties": {
        "year": {"type": "integer", "description": "Year, e.g. 2026"},
        "employee_id": {"type": "integer", "description": "Optional. Approvers/HR only."}},
     "required": ["year"]},
)
def list_leaves(ctx: UserContext, args: dict) -> dict:
    emp = _target_employee(ctx, args)
    year = int(args["year"])
    rows = query(
        "SELECT leave_type, date_from, date_to, number_of_days, state FROM ai.leaves "
        "WHERE employee_id = %s AND EXTRACT(YEAR FROM date_from) = %s "
        "ORDER BY date_from DESC LIMIT %s", (emp, year, MAX_ROWS))
    return {"employee_id": emp, "year": year, "leaves": rows}
