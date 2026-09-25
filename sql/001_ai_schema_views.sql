-- Schema `ai`: minimal read-only views over standard Odoo 19 tables.
-- No view exposes payroll, salaries or banking data. Revert with sql/999_rollback.sql.
-- Safe to run more than once.
CREATE SCHEMA IF NOT EXISTS ai;

-- Active employees (identity used to resolve "my leave").
CREATE OR REPLACE VIEW ai.employees AS
SELECT e.id AS employee_id, e.user_id, e.name, e.company_id, e.parent_id AS manager_employee_id
FROM hr_employee e
WHERE e.active;

-- Leave requests (hr.leave). Type names are translated JSON: prefer English, else any language.
CREATE OR REPLACE VIEW ai.leaves AS
SELECT l.id, l.employee_id, l.company_id,
       COALESCE(t.name ->> 'en_US', (SELECT v FROM jsonb_each_text(t.name) AS x(k, v) LIMIT 1)) AS leave_type,
       l.request_date_from AS date_from, l.request_date_to AS date_to,
       l.number_of_days, l.state
FROM hr_leave l
JOIN hr_leave_type t ON t.id = l.holiday_status_id;

-- Balance per employee and leave type: validated allocations minus validated leave.
-- DROP + CREATE because CREATE OR REPLACE cannot change a column's type.
DROP VIEW IF EXISTS ai.leave_balance;
CREATE VIEW ai.leave_balance AS
WITH alloc AS (
    SELECT employee_id, holiday_status_id, SUM(number_of_days) AS allocated
    FROM hr_leave_allocation WHERE state = 'validate' AND employee_id IS NOT NULL
    GROUP BY 1, 2
), taken AS (
    SELECT employee_id, holiday_status_id, SUM(number_of_days) AS taken
    FROM hr_leave WHERE state IN ('validate', 'validate1')
    GROUP BY 1, 2
)
SELECT a.employee_id,
       COALESCE(t.name ->> 'en_US', (SELECT v FROM jsonb_each_text(t.name) AS x(k, v) LIMIT 1)) AS leave_type,
       ROUND(a.allocated::numeric, 2) AS allocated,
       ROUND(COALESCE(k.taken, 0)::numeric, 2) AS taken,
       ROUND((a.allocated - COALESCE(k.taken, 0))::numeric, 2) AS remaining
FROM alloc a
JOIN hr_leave_type t ON t.id = a.holiday_status_id
LEFT JOIN taken k ON k.employee_id = a.employee_id AND k.holiday_status_id = a.holiday_status_id;

-- Sales orders.
CREATE OR REPLACE VIEW ai.sales_orders AS
SELECT s.id, s.name, s.company_id, c.name AS company, p.name AS customer,
       s.date_order::date AS order_date, s.state, s.amount_untaxed, s.amount_total,
       cur.name AS currency
FROM sale_order s
JOIN res_company c ON c.id = s.company_id
JOIN res_partner p ON p.id = s.partner_id
JOIN res_currency cur ON cur.id = s.currency_id;

-- Customer and vendor invoices. invoice_date can be empty on imported history, so fall back
-- to the accounting date.
CREATE OR REPLACE VIEW ai.invoices AS
SELECT m.id, m.name, m.company_id, c.name AS company, p.name AS partner, m.move_type,
       COALESCE(m.invoice_date, m.date) AS invoice_date, m.invoice_date_due AS due_date,
       m.state, m.payment_state, m.amount_untaxed, m.amount_total, m.amount_residual,
       cur.name AS currency
FROM account_move m
JOIN res_company c ON c.id = m.company_id
LEFT JOIN res_partner p ON p.id = m.partner_id
JOIN res_currency cur ON cur.id = m.currency_id
WHERE m.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund');
