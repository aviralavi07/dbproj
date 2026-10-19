"""Server-side input validation. Every function returns (clean_values, errors)."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z0-9-]+$")
PHONE_RE = re.compile(r"^\+?\d{10,15}$")

ISSUE_TYPES = ["Billing", "Technical", "Account"]
PRIORITIES = ["Low", "Medium", "High"]
TICKET_STATUSES = ["Open", "In Progress", "Resolved"]
PAYMENT_METHODS = ["Card", "UPI", "Net Banking", "Bank Transfer"]
PAYMENT_STATUSES = ["Success", "Failed", "Pending"]
REFUND_STATUSES = ["Requested", "Approved", "Processed"]
INVOICE_STATUSES = ["Pending", "Paid", "Overdue"]
SUB_STATUSES = ["Active", "Expired", "Cancelled"]


def text(form, key):
    return (form.get(key) or "").strip()


def as_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def as_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def as_money(value):
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError):
        return None
    if not d.is_finite() or d != d.quantize(Decimal("0.01")):
        return None                      # more than 2 decimal places
    return d.quantize(Decimal("0.01"))


def require_date(form, key, label, errors):
    value = as_date(text(form, key))
    if value is None:
        errors[key] = "%s must be a valid date (YYYY-MM-DD)." % label
    return value


def validate_client(form):
    e, v = {}, {}
    v["company"] = text(form, "company")
    v["contact"] = text(form, "contact")
    v["email"] = text(form, "email")
    v["phone"] = text(form, "phone")
    v["auto_renew"] = 1 if form.get("auto_renew") else 0
    if not v["company"]:
        e["company"] = "Company name is required."
    elif len(v["company"]) > 100:
        e["company"] = "Company name can have at most 100 characters."
    if not v["contact"]:
        e["contact"] = "Contact person is required."
    elif len(v["contact"]) > 80:
        e["contact"] = "Contact person can have at most 80 characters."
    if not v["email"]:
        e["email"] = "E-mail is required."
    elif not EMAIL_RE.match(v["email"]) or len(v["email"]) > 100:
        e["email"] = "Enter a valid e-mail address (for example name@company.com)."
    if v["phone"] and not PHONE_RE.match(v["phone"]):
        e["phone"] = "Phone must contain 10 to 15 digits (an optional leading + is allowed)."
    v["signup"] = require_date(form, "signup", "Signup date", e)
    if v["signup"] and v["signup"] > date.today():
        e["signup"] = "Signup date cannot be in the future."
    return v, e


def validate_tier(form):
    e, v = {}, {}
    v["name"] = text(form, "name")
    if not v["name"]:
        e["name"] = "Plan name is required."
    elif len(v["name"]) > 50:
        e["name"] = "Plan name can have at most 50 characters."
    v["rate"] = as_money(text(form, "rate"))
    if v["rate"] is None or v["rate"] <= 0:
        e["rate"] = "Monthly rate must be a positive amount with at most 2 decimals."
    v["users"] = as_int(text(form, "users"))
    if v["users"] is None or v["users"] <= 0:
        e["users"] = "Maximum users must be a whole number greater than 0."
    v["storage"] = as_int(text(form, "storage"))
    if v["storage"] is None or v["storage"] <= 0:
        e["storage"] = "Storage must be a whole number of GB greater than 0."
    return v, e


def validate_subscription(form):
    e, v = {}, {}
    v["client"] = as_int(text(form, "client"))
    v["tier"] = as_int(text(form, "tier"))
    if v["client"] is None:
        e["client"] = "Select a client."
    if v["tier"] is None:
        e["tier"] = "Select a pricing tier."
    v["start"] = require_date(form, "start", "Start date", e)
    v["end"] = None
    if text(form, "end"):
        v["end"] = require_date(form, "end", "End date", e)
        if v["end"] and v["start"] and v["end"] < v["start"]:
            e["end"] = "End date cannot be before the start date."
    return v, e


def validate_cancellation(form, start_date):
    e, v = {}, {}
    v["request"] = require_date(form, "request", "Request date", e)
    v["effective"] = require_date(form, "effective", "Effective date", e)
    v["reason"] = text(form, "reason")
    if len(v["reason"]) > 150:
        e["reason"] = "Reason can have at most 150 characters."
    if v["request"] and v["effective"] and v["effective"] < v["request"]:
        e["effective"] = "Effective date cannot be before the request date."
    if v["effective"] and start_date and v["effective"] < as_date(start_date):
        e["effective"] = "Effective date cannot be before the subscription start date."
    return v, e


def validate_invoice(form):
    e, v = {}, {}
    v["subscription"] = as_int(text(form, "subscription"))
    if v["subscription"] is None:
        e["subscription"] = "Select a subscription."
    v["invoice_date"] = require_date(form, "invoice_date", "Invoice date", e)
    v["due_date"] = require_date(form, "due_date", "Due date", e)
    if v["invoice_date"] and v["due_date"] and v["due_date"] < v["invoice_date"]:
        e["due_date"] = "Due date cannot be before the invoice date."
    items = []
    for i in range(1, 6):
        desc = text(form, "desc%d" % i)
        qty_raw, price_raw = text(form, "qty%d" % i), text(form, "price%d" % i)
        if not (desc or qty_raw or price_raw):
            continue                                   # empty line is ignored
        qty, price = as_int(qty_raw), as_money(price_raw)
        if not desc:
            e["line%d" % i] = "Line %d: description is required." % i
        elif len(desc) > 150:
            e["line%d" % i] = "Line %d: description can have at most 150 characters." % i
        elif qty is None or qty <= 0:
            e["line%d" % i] = "Line %d: quantity must be a whole number greater than 0." % i
        elif price is None or price < 0:
            e["line%d" % i] = "Line %d: unit price must be 0 or more, with at most 2 decimals." % i
        else:
            items.append((desc, qty, price, (price * qty).quantize(Decimal("0.01"))))
    v["items"] = items
    if not items and not any(k.startswith("line") for k in e):
        e["items"] = "Add at least one invoice line."
    return v, e


def validate_payment(form, balance_due):
    e, v = {}, {}
    v["date"] = require_date(form, "date", "Payment date", e)
    v["method"] = text(form, "method")
    if v["method"] not in PAYMENT_METHODS:
        e["method"] = "Select a payment method."
    v["status"] = text(form, "status")
    if v["status"] not in PAYMENT_STATUSES:
        e["status"] = "Select a payment status."
    v["amount"] = as_money(text(form, "amount"))
    if v["amount"] is None or v["amount"] <= 0:
        e["amount"] = "Amount must be greater than 0 (at most 2 decimals)."
    elif v["status"] == "Success" and v["amount"] > Decimal(str(balance_due)).quantize(Decimal("0.01")):
        e["amount"] = "Amount is more than the balance due (%.2f)." % balance_due
    return v, e


def validate_refund(form, refundable):
    e, v = {}, {}
    v["date"] = require_date(form, "date", "Refund date", e)
    v["reason"] = text(form, "reason")
    if len(v["reason"]) > 150:
        e["reason"] = "Reason can have at most 150 characters."
    v["status"] = text(form, "status")
    if v["status"] not in REFUND_STATUSES:
        e["status"] = "Select a refund status."
    v["amount"] = as_money(text(form, "amount"))
    if v["amount"] is None or v["amount"] <= 0:
        e["amount"] = "Refund amount must be greater than 0 (at most 2 decimals)."
    elif v["amount"] > Decimal(str(refundable)).quantize(Decimal("0.01")):
        e["amount"] = "Refund is more than the refundable amount (%.2f)." % refundable
    return v, e


def validate_ticket(form):
    e, v = {}, {}
    v["client"] = as_int(text(form, "client"))
    if v["client"] is None:
        e["client"] = "Select a client."
    v["issue"] = text(form, "issue")
    if v["issue"] not in ISSUE_TYPES:
        e["issue"] = "Select an issue type."
    v["priority"] = text(form, "priority")
    if v["priority"] not in PRIORITIES:
        e["priority"] = "Select a priority."
    v["status"] = text(form, "status")
    if v["status"] not in TICKET_STATUSES:
        e["status"] = "Select a status."
    v["created"] = require_date(form, "created", "Created date", e)
    if v["created"] and v["created"] > date.today():
        e["created"] = "Created date cannot be in the future."
    return v, e


def validate_usage(form):
    e, v = {}, {}
    v["subscription"] = as_int(text(form, "subscription"))
    if v["subscription"] is None:
        e["subscription"] = "Select a subscription."
    v["users"] = as_int(text(form, "users"))
    if v["users"] is None or v["users"] < 0:
        e["users"] = "Active users must be a whole number, 0 or more."
    v["storage"] = as_money(text(form, "storage"))
    if v["storage"] is None or v["storage"] < 0:
        e["storage"] = "Storage used must be 0 or more (at most 2 decimals)."
    v["date"] = require_date(form, "date", "Usage date", e)
    return v, e
