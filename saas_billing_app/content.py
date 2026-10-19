"""Fixed text and tables shown on the presentation pages of the website."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

ENTITIES = [
    ("CLIENT", "Client_ID", "Company_Name, Contact_Person, Email, Phone, Signup_Date, Auto_Renew"),
    ("PRICING_TIER", "Tier_ID", "Tier_Name, Monthly_Rate, Max_Users, Storage_GB"),
    ("SUBSCRIPTION", "Subscription_ID", "Client_ID (FK), Tier_ID (FK), Start_Date, End_Date, Status"),
    ("CANCELLATION", "Cancellation_ID", "Subscription_ID (FK, unique), Request_Date, Effective_Date, Reason"),
    ("SUPPORT_TICKET", "Ticket_ID", "Client_ID (FK), Issue_Type, Priority, Ticket_Status, Created_Date, Resolved_Date"),
    ("INVOICE", "Invoice_ID", "Subscription_ID (FK), Invoice_Date, Due_Date, Total_Amount, Invoice_Status"),
    ("INVOICE_ITEM", "Item_ID", "Invoice_ID (FK), Description, Quantity, Unit_Price, Amount"),
    ("PAYMENT", "Payment_ID", "Invoice_ID (FK), Payment_Date, Payment_Method, Amount_Paid, Status"),
    ("REFUND", "Refund_ID", "Payment_ID (FK), Refund_Date, Refund_Amount, Reason, Refund_Status"),
    ("USAGE_RECORD", "Usage_ID", "Subscription_ID (FK), Active_Users, Storage_Used_GB, Usage_Date"),
]

RELATIONSHIPS = [
    ("Subscribes", "CLIENT to SUBSCRIPTION", "1 : N", "SUBSCRIPTION.Client_ID"),
    ("Defines", "PRICING_TIER to SUBSCRIPTION", "1 : N", "SUBSCRIPTION.Tier_ID"),
    ("Cancelled By", "SUBSCRIPTION to CANCELLATION", "1 : 1", "CANCELLATION.Subscription_ID (unique)"),
    ("Raises", "CLIENT to SUPPORT_TICKET", "1 : N", "SUPPORT_TICKET.Client_ID"),
    ("Generates", "SUBSCRIPTION to INVOICE", "1 : N", "INVOICE.Subscription_ID"),
    ("Contains", "INVOICE to INVOICE_ITEM", "1 : N", "INVOICE_ITEM.Invoice_ID (cascade on delete)"),
    ("Receives", "INVOICE to PAYMENT", "1 : N", "PAYMENT.Invoice_ID"),
    ("Refunded By", "PAYMENT to REFUND", "1 : N", "REFUND.Payment_ID"),
    ("Records", "SUBSCRIPTION to USAGE_RECORD", "1 : N", "USAGE_RECORD.Subscription_ID"),
]

MODULES = [
    ("Dashboard", "dashboard", "Totals for clients, subscriptions, billing and tickets, and revenue by plan."),
    ("Clients", "clients", "Search, add, edit and delete clients. A client with subscriptions cannot be deleted."),
    ("Plans", "tiers", "Manage pricing plans with a monthly rate, a user limit and a storage limit."),
    ("Subscriptions", "subscriptions", "Create subscriptions and cancel them with a date and a reason."),
    ("Invoices", "invoices", "Create itemized invoices, record payments and refunds, filter by status and date."),
    ("Support", "tickets", "Raise, filter, update and resolve support tickets."),
    ("Usage", "usage", "Record usage readings and see which ones cross the limit of the plan."),
    ("Reports", "reports", "Seven SQL queries that run on the database, shown with their results."),
]

REQUIREMENTS = [
    ("Simple user interface", "The application menu", "dashboard"),
    ("Database connectivity", "How the pieces fit, on this page", "home"),
    ("CRUD operations", "Clients page: add, edit and delete", "clients"),
    ("Search and retrieval", "Invoice filters and the client search box", "invoices"),
    ("Important SQL queries through the application", "Reports page", "reports"),
    ("Input validation", "Add client form, submitted with wrong values", "client_new"),
    ("Test cases", "Testing page", "testing"),
    ("Final database", "Database design page", "design"),
]


def load_tests(filename):
    """Read test IDs and descriptions from the docstrings of a test file."""
    path = os.path.join(HERE, "tests", filename)
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8").read()
    found = re.findall(r'def test_((?:TC|SC)\d+)_\w+\(self\):\s+"""([^"]+)"""', text)
    return sorted(found)


def load_views():
    """The view definitions from the final database script."""
    path = os.path.join(HERE, "database", "final_database.sql")
    if not os.path.exists(path):
        return ""
    text = open(path, encoding="utf-8").read()
    start = text.find("CREATE OR REPLACE VIEW")
    return text[start:].strip() if start >= 0 else ""
