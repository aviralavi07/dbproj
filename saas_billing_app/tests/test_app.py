"""Automated test cases for the Cloud SaaS Subscription and Billing Management System.

The tests run the real Flask application against a fresh copy of the final database
(SQLite copy of final_database.sql), so they never touch your MySQL data.
Every test starts from the same clean sample data.
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = tempfile.mkdtemp()
TEMPLATE_DB = os.path.join(TMP, "template.db")
WORK_DB = os.path.join(TMP, "work.db")

os.environ["DB_ENGINE"] = "sqlite"
os.environ["SQLITE_PATH"] = WORK_DB

# build the template database once from the final MySQL script
script = open(os.path.join(ROOT, "database", "final_database.sql"), encoding="utf-8").read()
script = re.sub(r"CREATE DATABASE[^;]*;|USE [^;]*;", "", script).replace("CREATE OR REPLACE VIEW", "CREATE VIEW")
_con = sqlite3.connect(TEMPLATE_DB)
_con.executescript(script)
_con.close()

import sys  # noqa: E402
sys.path.insert(0, ROOT)
import app as flask_app  # noqa: E402
import db  # noqa: E402


def rows(sql, params=()):
    return db.query(sql, params)


def count(table, where="1 = 1", params=()):
    return rows("SELECT COUNT(*) AS n FROM %s WHERE %s" % (table, where), params)[0]["n"]


class Base(unittest.TestCase):
    def setUp(self):
        shutil.copyfile(TEMPLATE_DB, WORK_DB)
        flask_app.app.config["TESTING"] = True
        self.c = flask_app.app.test_client()

    def get(self, url):
        r = self.c.get(url, follow_redirects=True)
        return r.status_code, r.get_data(as_text=True)

    def post(self, url, data=None):
        r = self.c.post(url, data=data or {}, follow_redirects=True)
        return r.status_code, r.get_data(as_text=True)

    client_ok = {"company": "Test Works Pvt Ltd", "contact": "Asha Verma", "email": "asha@testworks.example",
                 "phone": "9876543210", "signup": "2026-09-01", "auto_renew": "1"}


class TestReadAndSearch(Base):
    def test_TC01_dashboard_shows_summary(self):
        """Dashboard opens and shows totals from the database"""
        code, html = self.get("/dashboard")
        self.assertEqual(code, 200)
        self.assertIn("Active subscriptions", html)
        self.assertIn("165,380.00", html)            # total billed
        self.assertIn("Enterprise", html)            # from view vw_tier_revenue

    def test_TC02_client_list_shows_all_clients(self):
        """Client list shows all 10 clients"""
        code, html = self.get("/clients")
        self.assertIn("10 client(s) shown", html)

    def test_TC03_search_client_by_company(self):
        """Search clients by part of the company name"""
        _, html = self.get("/clients?q=nexo")
        self.assertIn("Nexora Technologies", html)
        self.assertIn("1 client(s) shown", html)

    def test_TC04_search_client_by_email(self):
        """Search clients by e-mail text"""
        _, html = self.get("/clients?q=freshbasket")
        self.assertIn("FreshBasket Foods", html)
        self.assertIn("1 client(s) shown", html)

    def test_TC05_search_with_no_match(self):
        """Search with no match shows an empty-result message"""
        _, html = self.get("/clients?q=zzzzzz")
        self.assertIn("No clients found", html)

    def test_TC06_filter_clients_by_auto_renew(self):
        """Filter clients whose auto-renew is off"""
        _, html = self.get("/clients?renew=0")
        self.assertIn("3 client(s) shown", html)

    def test_TC07_client_detail_page(self):
        """Client detail page lists subscriptions and tickets"""
        _, html = self.get("/clients/1")
        self.assertIn("Nexora Technologies", html)
        self.assertIn("Growth", html)
        self.assertIn("Starter", html)

    def test_TC08_unknown_record_gives_404(self):
        """Opening a client that does not exist shows a not-found page"""
        code, html = self.get("/clients/999")
        self.assertEqual(code, 404)
        self.assertIn("not found", html)


class TestClientCrud(Base):
    def test_TC09_add_client_valid(self):
        """Create: a valid client is saved with the next ID"""
        _, html = self.post("/clients/new", self.client_ok)
        self.assertIn("Client added (ID 11)", html)
        self.assertEqual(count("CLIENT"), 11)
        self.assertEqual(rows("SELECT Company_Name FROM CLIENT WHERE Client_ID = 11")[0]["Company_Name"], "Test Works Pvt Ltd")

    def test_TC10_add_client_missing_company(self):
        """Validation: company name is required"""
        data = dict(self.client_ok, company="")
        _, html = self.post("/clients/new", data)
        self.assertIn("Company name is required", html)
        self.assertEqual(count("CLIENT"), 10)

    def test_TC11_add_client_invalid_email(self):
        """Validation: e-mail must have a valid format"""
        _, html = self.post("/clients/new", dict(self.client_ok, email="not-an-email"))
        self.assertIn("valid e-mail", html)
        self.assertEqual(count("CLIENT"), 10)

    def test_TC12_add_client_invalid_phone(self):
        """Validation: phone must be 10 to 15 digits"""
        _, html = self.post("/clients/new", dict(self.client_ok, phone="12ab"))
        self.assertIn("Phone must contain 10 to 15 digits", html)
        self.assertEqual(count("CLIENT"), 10)

    def test_TC13_add_client_future_date(self):
        """Validation: signup date cannot be in the future"""
        _, html = self.post("/clients/new", dict(self.client_ok, signup="2999-01-01"))
        self.assertIn("cannot be in the future", html)
        self.assertEqual(count("CLIENT"), 10)

    def test_TC14_add_client_duplicate_email(self):
        """Database UNIQUE constraint: duplicate e-mail is rejected with a clear message"""
        _, html = self.post("/clients/new", dict(self.client_ok, email="ravi.menon@nexora.example"))
        self.assertIn("already exists", html)
        self.assertEqual(count("CLIENT"), 10)

    def test_TC15_update_client(self):
        """Update: editing a client changes the stored data"""
        data = dict(self.client_ok, company="Nexora Technologies Ltd", email="ravi.menon@nexora.example")
        _, html = self.post("/clients/1/edit", data)
        self.assertIn("Client updated", html)
        self.assertEqual(rows("SELECT Company_Name FROM CLIENT WHERE Client_ID = 1")[0]["Company_Name"], "Nexora Technologies Ltd")

    def test_TC16_update_client_duplicate_email(self):
        """Update with another client's e-mail is rejected"""
        data = dict(self.client_ok, email="priya.nair@blueleaf.example")
        _, html = self.post("/clients/1/edit", data)
        self.assertIn("already exists", html)
        self.assertEqual(rows("SELECT Email FROM CLIENT WHERE Client_ID = 1")[0]["Email"], "ravi.menon@nexora.example")

    def test_TC17_delete_client_without_dependants(self):
        """Delete: a client with no subscriptions or tickets can be deleted"""
        self.post("/clients/new", self.client_ok)
        _, html = self.post("/clients/11/delete")
        self.assertIn("Client deleted", html)
        self.assertEqual(count("CLIENT"), 10)

    def test_TC18_delete_client_with_subscriptions_blocked(self):
        """Foreign key RESTRICT: a client with subscriptions cannot be deleted"""
        _, html = self.post("/clients/1/delete")
        self.assertIn("cannot be deleted", html)
        self.assertEqual(count("CLIENT"), 10)


class TestTiers(Base):
    def test_TC19_add_tier(self):
        """Create a new pricing plan"""
        _, html = self.post("/tiers/new", {"name": "Platinum", "rate": "39999.00", "users": "1000", "storage": "5000"})
        self.assertIn("Pricing tier added", html)
        self.assertEqual(count("PRICING_TIER"), 5)

    def test_TC20_tier_negative_rate_rejected(self):
        """Validation: plan rate must be positive"""
        _, html = self.post("/tiers/new", {"name": "Bad", "rate": "-5", "users": "10", "storage": "10"})
        self.assertIn("positive amount", html)
        self.assertEqual(count("PRICING_TIER"), 4)

    def test_TC21_edit_tier_keeps_old_invoice_prices(self):
        """Changing a plan rate does not change old invoice amounts"""
        before = rows("SELECT Total_Amount FROM INVOICE WHERE Invoice_ID = 1")[0]["Total_Amount"]
        self.post("/tiers/2/edit", {"name": "Growth", "rate": "5999.00", "users": "50", "storage": "200"})
        self.assertEqual(rows("SELECT Monthly_Rate FROM PRICING_TIER WHERE Tier_ID = 2")[0]["Monthly_Rate"], 5999.0)
        self.assertEqual(rows("SELECT Total_Amount FROM INVOICE WHERE Invoice_ID = 1")[0]["Total_Amount"], before)

    def test_TC22_delete_used_tier_blocked(self):
        """A plan that has subscriptions cannot be deleted"""
        _, html = self.post("/tiers/1/delete")
        self.assertIn("cannot be deleted", html)
        self.assertEqual(count("PRICING_TIER"), 4)


class TestSubscriptions(Base):
    def test_TC23_create_subscription(self):
        """Create a subscription for a client"""
        _, html = self.post("/subscriptions/new", {"client": "8", "tier": "2", "start": "2026-10-01"})
        self.assertIn("Subscription created (ID 13)", html)
        self.assertEqual(rows("SELECT Status FROM SUBSCRIPTION WHERE Subscription_ID = 13")[0]["Status"], "Active")

    def test_TC24_subscription_end_before_start_rejected(self):
        """Validation: end date cannot be before start date"""
        _, html = self.post("/subscriptions/new", {"client": "8", "tier": "2", "start": "2026-10-10", "end": "2026-10-01"})
        self.assertIn("End date cannot be before the start date", html)
        self.assertEqual(count("SUBSCRIPTION"), 12)

    def test_TC25_filter_subscriptions_by_status(self):
        """Filter subscriptions by status Cancelled"""
        _, html = self.get("/subscriptions?status=Cancelled")
        self.assertIn("2 subscription(s) shown", html)

    def test_TC26_cancel_subscription_transaction(self):
        """Cancel: inserts a CANCELLATION row and updates the subscription together"""
        _, html = self.post("/subscriptions/1/cancel", {"request": "2026-10-01", "effective": "2026-10-15", "reason": "Test"})
        self.assertIn("Subscription 1 cancelled", html)
        sub = rows("SELECT Status, End_Date FROM SUBSCRIPTION WHERE Subscription_ID = 1")[0]
        self.assertEqual((sub["Status"], sub["End_Date"]), ("Cancelled", "2026-10-15"))
        self.assertEqual(count("CANCELLATION", "Subscription_ID = 1"), 1)

    def test_TC27_cancel_effective_before_request_rejected(self):
        """Validation: effective date cannot be before request date; nothing changes"""
        _, html = self.post("/subscriptions/1/cancel", {"request": "2026-10-10", "effective": "2026-10-01"})
        self.assertIn("cannot be before the request date", html)
        self.assertEqual(rows("SELECT Status FROM SUBSCRIPTION WHERE Subscription_ID = 1")[0]["Status"], "Active")
        self.assertEqual(count("CANCELLATION"), 2)

    def test_TC28_cancel_non_active_blocked(self):
        """An already cancelled subscription cannot be cancelled again"""
        _, html = self.get("/subscriptions/5/cancel")
        self.assertIn("Only an Active subscription can be cancelled", html)


class TestInvoicesAndPayments(Base):
    inv = {"subscription": "1", "invoice_date": "2026-10-01", "due_date": "2026-10-16",
           "desc1": "Monthly plan fee - Growth", "qty1": "1", "price1": "4999.00",
           "desc2": "Extra storage (100 GB)", "qty2": "2", "price2": "750.00"}

    def test_TC29_create_invoice_with_items(self):
        """Create invoice: lines saved, amounts and total calculated"""
        _, html = self.post("/invoices/new", self.inv)
        self.assertIn("Invoice 21 created", html)
        self.assertEqual(rows("SELECT Total_Amount FROM INVOICE WHERE Invoice_ID = 21")[0]["Total_Amount"], 6499.0)
        self.assertEqual(count("INVOICE_ITEM", "Invoice_ID = 21"), 2)
        self.assertEqual(rows("SELECT Amount FROM INVOICE_ITEM WHERE Invoice_ID = 21 AND Quantity = 2")[0]["Amount"], 1500.0)

    def test_TC30_invoice_invalid_line_saves_nothing(self):
        """Validation: a bad line (quantity 0) rejects the whole invoice"""
        _, html = self.post("/invoices/new", dict(self.inv, qty2="0"))
        self.assertIn("quantity must be a whole number greater than 0", html)
        self.assertEqual(count("INVOICE"), 20)

    def test_TC31_invoice_due_before_invoice_date_rejected(self):
        """Validation: due date cannot be before invoice date"""
        _, html = self.post("/invoices/new", dict(self.inv, due_date="2026-09-01"))
        self.assertIn("Due date cannot be before the invoice date", html)
        self.assertEqual(count("INVOICE"), 20)

    def test_TC32_invoice_without_lines_rejected(self):
        """Validation: at least one invoice line is needed"""
        data = {k: v for k, v in self.inv.items() if not k[-1] in "12"}
        _, html = self.post("/invoices/new", data)
        self.assertIn("Add at least one invoice line", html)

    def test_TC33_filter_invoices_by_status(self):
        """Filter invoices by status Overdue"""
        _, html = self.get("/invoices?status=Overdue")
        self.assertIn("3 invoice(s) shown", html)

    def test_TC34_filter_invoices_by_client_and_dates(self):
        """Filter invoices by client name and invoice date range"""
        _, html = self.get("/invoices?q=Apex&from=2026-09-01&to=2026-09-30")
        self.assertIn("2 invoice(s) shown", html)

    def test_TC35_invoice_detail_shows_balance(self):
        """Invoice detail shows items, payments and balance due"""
        _, html = self.get("/invoices/14")
        self.assertIn("Extra users (10 users)", html)
        self.assertIn("2,599.00", html)
        self.assertIn("Record a payment", html)

    def test_TC36_full_payment_marks_invoice_paid(self):
        """Payment of the full balance changes invoice status to Paid (transaction)"""
        _, html = self.post("/invoices/14/pay", {"date": "2026-10-02", "method": "UPI", "amount": "2599.00", "status": "Success"})
        self.assertIn("Payment 17 recorded", html)
        self.assertEqual(rows("SELECT Invoice_Status FROM INVOICE WHERE Invoice_ID = 14")[0]["Invoice_Status"], "Paid")

    def test_TC37_partial_payment_keeps_status(self):
        """A part payment is stored but the invoice is not marked Paid"""
        self.post("/invoices/14/pay", {"date": "2026-10-02", "method": "Card", "amount": "1000.00", "status": "Success"})
        self.assertEqual(rows("SELECT Invoice_Status FROM INVOICE WHERE Invoice_ID = 14")[0]["Invoice_Status"], "Pending")
        _, html = self.get("/invoices/14")
        self.assertIn("1,599.00", html)

    def test_TC38_overpayment_rejected(self):
        """Validation: payment cannot be more than the balance due"""
        _, html = self.post("/invoices/14/pay", {"date": "2026-10-02", "method": "UPI", "amount": "9999.00", "status": "Success"})
        self.assertIn("more than the balance due", html)
        self.assertEqual(count("PAYMENT"), 16)

    def test_TC39_failed_payment_does_not_reduce_balance(self):
        """A Failed payment is recorded but the invoice stays unpaid"""
        self.post("/invoices/14/pay", {"date": "2026-10-02", "method": "Card", "amount": "2599.00", "status": "Failed"})
        self.assertEqual(count("PAYMENT", "Invoice_ID = 14"), 1)
        self.assertEqual(rows("SELECT Invoice_Status FROM INVOICE WHERE Invoice_ID = 14")[0]["Invoice_Status"], "Pending")

    def test_TC40_invalid_payment_method_rejected(self):
        """Validation: payment method must be one of the allowed values"""
        _, html = self.post("/invoices/14/pay", {"date": "2026-10-02", "method": "Cash", "amount": "100.00", "status": "Success"})
        self.assertIn("Select a payment method", html)

    def test_TC41_refund_recorded(self):
        """Refund against a successful payment is saved"""
        _, html = self.post("/payments/1/refund", {"date": "2026-10-02", "amount": "500.00", "reason": "Test", "status": "Requested"})
        self.assertIn("Refund 4 recorded", html)
        self.assertEqual(count("REFUND", "Payment_ID = 1"), 1)

    def test_TC42_refund_more_than_payment_rejected(self):
        """Validation: total refunds cannot exceed the payment amount"""
        _, html = self.post("/payments/1/refund", {"date": "2026-10-02", "amount": "9999.00", "reason": "", "status": "Requested"})
        self.assertIn("more than the refundable amount", html)
        self.assertEqual(count("REFUND"), 3)

    def test_TC43_refund_on_failed_payment_blocked(self):
        """Only a successful payment can be refunded"""
        _, html = self.post("/payments/6/refund", {"date": "2026-10-02", "amount": "100.00", "reason": "", "status": "Requested"})
        self.assertIn("Only a successful payment can be refunded", html)

    def test_TC44_delete_invoice_cascades_items(self):
        """Delete an unpaid invoice: its items are deleted by ON DELETE CASCADE"""
        _, html = self.post("/invoices/14/delete")
        self.assertIn("Invoice deleted", html)
        self.assertEqual(count("INVOICE_ITEM", "Invoice_ID = 14"), 0)

    def test_TC45_delete_invoice_with_payment_blocked(self):
        """Foreign key RESTRICT: an invoice that has payments cannot be deleted"""
        _, html = self.post("/invoices/1/delete")
        self.assertEqual(count("INVOICE", "Invoice_ID = 1"), 1)

    def test_TC46_mark_overdue_updates_status(self):
        """Pending invoices past their due date are marked Overdue"""
        self.post("/invoices/new", dict(self.inv, invoice_date="2020-01-01", due_date="2020-01-15"))
        _, html = self.post("/invoices/mark-overdue")
        self.assertIn("marked Overdue", html)
        self.assertEqual(rows("SELECT Invoice_Status FROM INVOICE WHERE Invoice_ID = 21")[0]["Invoice_Status"], "Overdue")


class TestTicketsUsageReports(Base):
    ticket = {"client": "8", "issue": "Billing", "priority": "High", "status": "Open", "created": "2026-10-01"}

    def test_TC47_create_ticket(self):
        """Create a support ticket"""
        _, html = self.post("/tickets/new", self.ticket)
        self.assertIn("Ticket 11 raised", html)

    def test_TC48_resolving_ticket_sets_resolved_date(self):
        """Update: setting a ticket to Resolved fills in Resolved_Date"""
        self.post("/tickets/3/edit", {"client": "3", "issue": "Billing", "priority": "Low", "status": "Resolved", "created": "2026-09-22"})
        row = rows("SELECT Ticket_Status, Resolved_Date FROM SUPPORT_TICKET WHERE Ticket_ID = 3")[0]
        self.assertEqual(row["Ticket_Status"], "Resolved")
        self.assertIsNotNone(row["Resolved_Date"])

    def test_TC49_filter_tickets_by_priority(self):
        """Filter tickets by priority High"""
        _, html = self.get("/tickets?priority=High")
        self.assertIn("3 ticket(s) shown", html)

    def test_TC50_invalid_ticket_priority_rejected(self):
        """Validation: ticket priority must be Low, Medium or High"""
        _, html = self.post("/tickets/new", dict(self.ticket, priority="Urgent"))
        self.assertIn("Select a priority", html)
        self.assertEqual(count("SUPPORT_TICKET"), 10)

    def test_TC51_delete_ticket(self):
        """Delete a support ticket"""
        _, html = self.post("/tickets/10/delete")
        self.assertIn("Ticket deleted", html)
        self.assertEqual(count("SUPPORT_TICKET"), 9)

    def test_TC52_add_usage_reading(self):
        """Create a usage reading"""
        _, html = self.post("/usage/new", {"subscription": "1", "users": "30", "storage": "120.50", "date": "2026-10-05"})
        self.assertIn("Usage record added", html)
        self.assertEqual(count("USAGE_RECORD"), 21)

    def test_TC53_usage_negative_users_rejected(self):
        """Validation: active users cannot be negative"""
        _, html = self.post("/usage/new", {"subscription": "1", "users": "-3", "storage": "10", "date": "2026-10-05"})
        self.assertIn("Active users must be a whole number", html)
        self.assertEqual(count("USAGE_RECORD"), 20)

    def test_TC54_usage_over_limit_flagged(self):
        """Usage list flags the subscription that crossed its storage limit"""
        _, html = self.get("/usage?sub=6")
        self.assertIn("Over limit", html)

    def test_TC55_reports_run_queries(self):
        """Reports page runs the 7 important queries and shows correct results"""
        _, html = self.get("/reports")
        self.assertEqual(html.count('class="sql"'), 7)
        self.assertIn("52248.00", html)               # Enterprise revenue (2 decimals)
        self.assertIn("EduSpark Learning", html)      # client with 0 tickets
        self.assertIn("Sundaram Textiles", html)      # overdue

    def test_TC56_sql_injection_attempt_is_harmless(self):
        """Security: SQL injection text in the search box is treated as plain text"""
        _, html = self.get("/clients?q=%27%3B+DROP+TABLE+CLIENT%3B+--")
        self.assertIn("No clients found", html)
        self.assertEqual(count("CLIENT"), 10)

    def test_TC57_database_constraint_blocks_bad_data(self):
        """Database CHECK constraint rejects an invalid status even if the app is bypassed"""
        with self.assertRaises(db.DB_ERRORS):
            db.execute("UPDATE INVOICE SET Invoice_Status = 'Waived' WHERE Invoice_ID = 1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
