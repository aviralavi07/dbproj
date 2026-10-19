"""Cloud SaaS Subscription and Billing Management System: Flask website and application.

Run with:   python app.py      (the browser opens http://127.0.0.1:5000 by itself)
"""
from datetime import date, timedelta
from decimal import Decimal

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for

import config
import content
import db
import validators as val

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


# ------------------------------------------------------------------ helpers
@app.template_filter("money")
def money(value):
    return "\u20b9 {:,.2f}".format(float(value or 0))


MONEY_COLUMNS = {"Revenue", "Total_Amount", "Amount_Paid", "Balance", "Storage_Used_GB"}


@app.template_filter("cell")
def cell(value, column=""):
    """Show a report value: amounts with 2 decimals (same in every database), empty as a dash."""
    if value is None:
        return "-"
    if column in MONEY_COLUMNS or isinstance(value, float):
        return "{:.2f}".format(float(value))
    return str(value)


@app.template_filter("badge")
def badge(value):
    good = {"Paid", "Active", "Resolved", "Success", "Processed", "Low", "OK"}
    bad = {"Overdue", "Cancelled", "Failed", "High", "Open", "Over limit"}
    if value in good:
        return "green"
    if value in bad:
        return "red"
    return "amber"


@app.context_processor
def inject_globals():
    return {"today": date.today().isoformat(), "db_name": config.MYSQL_DATABASE}


def today():
    return date.today().isoformat()


def clients_for_select():
    return db.query("SELECT Client_ID, Company_Name FROM CLIENT ORDER BY Company_Name")


def tiers_for_select():
    return db.query("SELECT Tier_ID, Tier_Name, Monthly_Rate FROM PRICING_TIER ORDER BY Monthly_Rate")


def subscriptions_for_select(only_active=True):
    sql = ("SELECT s.Subscription_ID, c.Company_Name, t.Tier_Name FROM SUBSCRIPTION s "
           "JOIN CLIENT c ON c.Client_ID = s.Client_ID JOIN PRICING_TIER t ON t.Tier_ID = s.Tier_ID")
    if only_active:
        sql += " WHERE s.Status = 'Active'"
    return db.query(sql + " ORDER BY c.Company_Name, s.Subscription_ID")


def show_errors(errors):
    for message in errors.values():
        flash(message, "error")


def invoice_summary(inv_id):
    """Invoice with client, plan and paid / balance amounts (or None)."""
    return db.one(
        "SELECT i.Invoice_ID, i.Subscription_ID, i.Invoice_Date, i.Due_Date, i.Total_Amount, i.Invoice_Status, "
        "c.Client_ID, c.Company_Name, t.Tier_Name, "
        "(SELECT COALESCE(SUM(p.Amount_Paid), 0) FROM PAYMENT p "
        " WHERE p.Invoice_ID = i.Invoice_ID AND p.Status = 'Success') AS Paid "
        "FROM INVOICE i JOIN SUBSCRIPTION s ON s.Subscription_ID = i.Subscription_ID "
        "JOIN CLIENT c ON c.Client_ID = s.Client_ID JOIN PRICING_TIER t ON t.Tier_ID = s.Tier_ID "
        "WHERE i.Invoice_ID = %s", (inv_id,))


def database_error(exc):
    return render_template("error.html", message=db.friendly_error(exc)), 500


for _exc in db.DB_ERRORS:
    app.register_error_handler(_exc, database_error)


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", message="Page or record not found."), 404


# ------------------------------------------------------- presentation pages
@app.route("/")
def home():
    return render_template("home.html", modules=content.MODULES, requirements=content.REQUIREMENTS)


@app.route("/design")
def design():
    return render_template("design.html", entities=content.ENTITIES, relationships=content.RELATIONSHIPS,
                           views=content.load_views())


@app.route("/testing")
def testing():
    return render_template("testing.html", tests=content.load_tests("test_app.py"),
                           site_tests=content.load_tests("test_site.py"))


@app.route("/team")
def team():
    return render_template("team.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico")


# ---------------------------------------------------------------- dashboard
@app.route("/dashboard")
def dashboard():
    kpi = {
        "clients": db.one("SELECT COUNT(*) AS n FROM CLIENT")["n"],
        "active": db.one("SELECT COUNT(*) AS n FROM SUBSCRIPTION WHERE Status = 'Active'")["n"],
        "billed": db.one("SELECT COALESCE(SUM(Total_Amount), 0) AS n FROM INVOICE")["n"],
        "received": db.one("SELECT COALESCE(SUM(Amount_Paid), 0) AS n FROM PAYMENT WHERE Status = 'Success'")["n"],
        "overdue": db.one("SELECT COUNT(*) AS n FROM INVOICE WHERE Invoice_Status = 'Overdue'")["n"],
        "tickets": db.one("SELECT COUNT(*) AS n FROM SUPPORT_TICKET WHERE Ticket_Status <> 'Resolved'")["n"],
    }
    tiers = db.query("SELECT Tier_Name, Subscriptions, Revenue FROM vw_tier_revenue ORDER BY Revenue DESC")
    recent = db.query(
        "SELECT i.Invoice_ID, c.Company_Name, i.Invoice_Date, i.Total_Amount, i.Invoice_Status "
        "FROM INVOICE i JOIN SUBSCRIPTION s ON s.Subscription_ID = i.Subscription_ID "
        "JOIN CLIENT c ON c.Client_ID = s.Client_ID "
        "ORDER BY i.Invoice_Date DESC, i.Invoice_ID DESC LIMIT 5")
    return render_template("dashboard.html", kpi=kpi, tiers=tiers, recent=recent)


# ------------------------------------------------------------------ clients
@app.route("/clients")
def clients():
    q = request.args.get("q", "").strip()
    renew = request.args.get("renew", "")
    sql = ("SELECT c.Client_ID, c.Company_Name, c.Contact_Person, c.Email, c.Phone, c.Signup_Date, c.Auto_Renew, "
           "(SELECT COUNT(*) FROM SUBSCRIPTION s WHERE s.Client_ID = c.Client_ID) AS Subs FROM CLIENT c WHERE 1 = 1")
    params = []
    if q:
        sql += " AND (c.Company_Name LIKE %s OR c.Contact_Person LIKE %s OR c.Email LIKE %s)"
        params += ["%" + q + "%"] * 3
    if renew in ("0", "1"):
        sql += " AND c.Auto_Renew = %s"
        params.append(int(renew))
    rows = db.query(sql + " ORDER BY c.Company_Name", params)
    return render_template("clients.html", rows=rows, q=q, renew=renew)


@app.route("/clients/new", methods=["GET", "POST"])
def client_new():
    form = request.form if request.method == "POST" else {"signup": today(), "auto_renew": "1"}
    if request.method == "POST":
        v, errors = val.validate_client(form)
        if not errors:
            try:
                with db.transaction() as tx:
                    new_id = tx.next_id("CLIENT")
                    tx.execute("INSERT INTO CLIENT (Client_ID, Company_Name, Contact_Person, Email, Phone, "
                               "Signup_Date, Auto_Renew) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                               (new_id, v["company"], v["contact"], v["email"], v["phone"] or None,
                                v["signup"].isoformat(), v["auto_renew"]))
                flash("Client added (ID %d)." % new_id, "ok")
                return redirect(url_for("clients"))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("client_form.html", form=form, mode="new", client_id=None)


@app.route("/clients/<int:cid>")
def client_detail(cid):
    client = db.one("SELECT * FROM CLIENT WHERE Client_ID = %s", (cid,))
    if not client:
        return not_found(None)
    subs = db.query("SELECT s.Subscription_ID, t.Tier_Name, s.Start_Date, s.End_Date, s.Status FROM SUBSCRIPTION s "
                    "JOIN PRICING_TIER t ON t.Tier_ID = s.Tier_ID WHERE s.Client_ID = %s ORDER BY s.Start_Date", (cid,))
    tickets = db.query("SELECT Ticket_ID, Issue_Type, Priority, Ticket_Status, Created_Date FROM SUPPORT_TICKET "
                       "WHERE Client_ID = %s ORDER BY Created_Date", (cid,))
    return render_template("client_detail.html", c=client, subs=subs, tickets=tickets)


@app.route("/clients/<int:cid>/edit", methods=["GET", "POST"])
def client_edit(cid):
    client = db.one("SELECT * FROM CLIENT WHERE Client_ID = %s", (cid,))
    if not client:
        return not_found(None)
    form = request.form if request.method == "POST" else {
        "company": client["Company_Name"], "contact": client["Contact_Person"], "email": client["Email"],
        "phone": client["Phone"] or "", "signup": client["Signup_Date"],
        "auto_renew": "1" if client["Auto_Renew"] else ""}
    if request.method == "POST":
        v, errors = val.validate_client(form)
        if not errors:
            try:
                db.execute("UPDATE CLIENT SET Company_Name = %s, Contact_Person = %s, Email = %s, Phone = %s, "
                           "Signup_Date = %s, Auto_Renew = %s WHERE Client_ID = %s",
                           (v["company"], v["contact"], v["email"], v["phone"] or None,
                            v["signup"].isoformat(), v["auto_renew"], cid))
                flash("Client updated.", "ok")
                return redirect(url_for("client_detail", cid=cid))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("client_form.html", form=form, mode="edit", client_id=cid)


@app.route("/clients/<int:cid>/delete", methods=["POST"])
def client_delete(cid):
    try:
        count = db.execute("DELETE FROM CLIENT WHERE Client_ID = %s", (cid,))
        flash("Client deleted." if count else "Client not found.", "ok" if count else "error")
        return redirect(url_for("clients"))
    except db.DB_ERRORS:
        flash("This client cannot be deleted because subscriptions or support tickets refer to it.", "error")
        return redirect(url_for("client_detail", cid=cid))


# --------------------------------------------------------------------- tiers
@app.route("/tiers")
def tiers():
    rows = db.query("SELECT t.Tier_ID, t.Tier_Name, t.Monthly_Rate, t.Max_Users, t.Storage_GB, "
                    "(SELECT COUNT(*) FROM SUBSCRIPTION s WHERE s.Tier_ID = t.Tier_ID) AS Subs "
                    "FROM PRICING_TIER t ORDER BY t.Monthly_Rate")
    return render_template("tiers.html", rows=rows)


@app.route("/tiers/new", methods=["GET", "POST"])
def tier_new():
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        v, errors = val.validate_tier(form)
        if not errors:
            try:
                with db.transaction() as tx:
                    new_id = tx.next_id("PRICING_TIER")
                    tx.execute("INSERT INTO PRICING_TIER (Tier_ID, Tier_Name, Monthly_Rate, Max_Users, Storage_GB) "
                               "VALUES (%s, %s, %s, %s, %s)",
                               (new_id, v["name"], str(v["rate"]), v["users"], v["storage"]))
                flash("Pricing tier added.", "ok")
                return redirect(url_for("tiers"))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("tier_form.html", form=form, mode="new", tier_id=None)


@app.route("/tiers/<int:tid>/edit", methods=["GET", "POST"])
def tier_edit(tid):
    tier = db.one("SELECT * FROM PRICING_TIER WHERE Tier_ID = %s", (tid,))
    if not tier:
        return not_found(None)
    form = request.form if request.method == "POST" else {
        "name": tier["Tier_Name"], "rate": "%.2f" % tier["Monthly_Rate"],
        "users": tier["Max_Users"], "storage": tier["Storage_GB"]}
    if request.method == "POST":
        v, errors = val.validate_tier(form)
        if not errors:
            try:
                db.execute("UPDATE PRICING_TIER SET Tier_Name = %s, Monthly_Rate = %s, Max_Users = %s, "
                           "Storage_GB = %s WHERE Tier_ID = %s",
                           (v["name"], str(v["rate"]), v["users"], v["storage"], tid))
                flash("Pricing tier updated. Old invoices keep their original prices.", "ok")
                return redirect(url_for("tiers"))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("tier_form.html", form=form, mode="edit", tier_id=tid)


@app.route("/tiers/<int:tid>/delete", methods=["POST"])
def tier_delete(tid):
    try:
        count = db.execute("DELETE FROM PRICING_TIER WHERE Tier_ID = %s", (tid,))
        flash("Pricing tier deleted." if count else "Tier not found.", "ok" if count else "error")
    except db.DB_ERRORS:
        flash("This tier cannot be deleted because subscriptions use it.", "error")
    return redirect(url_for("tiers"))


# ------------------------------------------------------------ subscriptions
@app.route("/subscriptions")
def subscriptions():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    sql = ("SELECT s.Subscription_ID, c.Company_Name, t.Tier_Name, t.Monthly_Rate, s.Start_Date, s.End_Date, s.Status "
           "FROM SUBSCRIPTION s JOIN CLIENT c ON c.Client_ID = s.Client_ID "
           "JOIN PRICING_TIER t ON t.Tier_ID = s.Tier_ID WHERE 1 = 1")
    params = []
    if q:
        sql += " AND c.Company_Name LIKE %s"
        params.append("%" + q + "%")
    if status in val.SUB_STATUSES:
        sql += " AND s.Status = %s"
        params.append(status)
    rows = db.query(sql + " ORDER BY s.Subscription_ID", params)
    return render_template("subscriptions.html", rows=rows, q=q, status=status, statuses=val.SUB_STATUSES)


@app.route("/subscriptions/new", methods=["GET", "POST"])
def subscription_new():
    form = request.form if request.method == "POST" else {"start": today()}
    if request.method == "POST":
        v, errors = val.validate_subscription(form)
        if not errors:
            try:
                with db.transaction() as tx:
                    new_id = tx.next_id("SUBSCRIPTION")
                    tx.execute("INSERT INTO SUBSCRIPTION (Subscription_ID, Client_ID, Tier_ID, Start_Date, End_Date, Status) "
                               "VALUES (%s, %s, %s, %s, %s, 'Active')",
                               (new_id, v["client"], v["tier"], v["start"].isoformat(),
                                v["end"].isoformat() if v["end"] else None))
                flash("Subscription created (ID %d)." % new_id, "ok")
                return redirect(url_for("subscriptions"))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("subscription_form.html", form=form, clients=clients_for_select(), tiers=tiers_for_select())


@app.route("/subscriptions/<int:sid>/cancel", methods=["GET", "POST"])
def subscription_cancel(sid):
    sub = db.one("SELECT s.Subscription_ID, s.Start_Date, s.Status, c.Company_Name, t.Tier_Name FROM SUBSCRIPTION s "
                 "JOIN CLIENT c ON c.Client_ID = s.Client_ID JOIN PRICING_TIER t ON t.Tier_ID = s.Tier_ID "
                 "WHERE s.Subscription_ID = %s", (sid,))
    if not sub:
        return not_found(None)
    if sub["Status"] != "Active":
        flash("Only an Active subscription can be cancelled.", "error")
        return redirect(url_for("subscriptions"))
    form = request.form if request.method == "POST" else {"request": today(), "effective": today()}
    if request.method == "POST":
        v, errors = val.validate_cancellation(form, sub["Start_Date"])
        if not errors:
            try:
                with db.transaction() as tx:      # both statements succeed or both are undone
                    new_id = tx.next_id("CANCELLATION")
                    tx.execute("INSERT INTO CANCELLATION (Cancellation_ID, Subscription_ID, Request_Date, "
                               "Effective_Date, Reason) VALUES (%s, %s, %s, %s, %s)",
                               (new_id, sid, v["request"].isoformat(), v["effective"].isoformat(), v["reason"] or None))
                    tx.execute("UPDATE SUBSCRIPTION SET Status = 'Cancelled', End_Date = %s WHERE Subscription_ID = %s",
                               (v["effective"].isoformat(), sid))
                flash("Subscription %d cancelled." % sid, "ok")
                return redirect(url_for("subscriptions"))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("cancel_form.html", sub=sub, form=form)


# ----------------------------------------------------------------- invoices
@app.route("/invoices")
def invoices():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()
    sql = ("SELECT i.Invoice_ID, c.Company_Name, t.Tier_Name, i.Invoice_Date, i.Due_Date, i.Total_Amount, "
           "i.Invoice_Status, (SELECT COALESCE(SUM(p.Amount_Paid), 0) FROM PAYMENT p "
           "WHERE p.Invoice_ID = i.Invoice_ID AND p.Status = 'Success') AS Paid "
           "FROM INVOICE i JOIN SUBSCRIPTION s ON s.Subscription_ID = i.Subscription_ID "
           "JOIN CLIENT c ON c.Client_ID = s.Client_ID JOIN PRICING_TIER t ON t.Tier_ID = s.Tier_ID WHERE 1 = 1")
    params = []
    if q:
        sql += " AND c.Company_Name LIKE %s"
        params.append("%" + q + "%")
    if status in val.INVOICE_STATUSES:
        sql += " AND i.Invoice_Status = %s"
        params.append(status)
    if val.as_date(date_from):
        sql += " AND i.Invoice_Date >= %s"
        params.append(date_from)
    if val.as_date(date_to):
        sql += " AND i.Invoice_Date <= %s"
        params.append(date_to)
    for raw in (date_from, date_to):
        if raw and not val.as_date(raw):
            flash("Filter dates must be in YYYY-MM-DD format; '%s' was ignored." % raw, "error")
    rows = db.query(sql + " ORDER BY i.Invoice_ID", params)
    return render_template("invoices.html", rows=rows, q=q, status=status, date_from=date_from, date_to=date_to,
                           statuses=val.INVOICE_STATUSES)


@app.route("/invoices/mark-overdue", methods=["POST"])
def invoices_mark_overdue():
    count = db.execute("UPDATE INVOICE SET Invoice_Status = 'Overdue' "
                       "WHERE Invoice_Status = 'Pending' AND Due_Date < %s", (today(),))
    flash("%d pending invoice(s) past their due date were marked Overdue." % count, "ok")
    return redirect(url_for("invoices"))


@app.route("/invoices/new", methods=["GET", "POST"])
def invoice_new():
    form = request.form if request.method == "POST" else {
        "invoice_date": today(), "due_date": (date.today() + timedelta(days=15)).isoformat()}
    if request.method == "POST":
        v, errors = val.validate_invoice(form)
        if not errors:
            try:
                with db.transaction() as tx:      # invoice and all its lines are saved together
                    inv_id = tx.next_id("INVOICE")
                    total = sum((it[3] for it in v["items"]), Decimal("0.00"))
                    tx.execute("INSERT INTO INVOICE (Invoice_ID, Subscription_ID, Invoice_Date, Due_Date, "
                               "Total_Amount, Invoice_Status) VALUES (%s, %s, %s, %s, %s, 'Pending')",
                               (inv_id, v["subscription"], v["invoice_date"].isoformat(),
                                v["due_date"].isoformat(), str(total)))
                    item_id = tx.next_id("INVOICE_ITEM")
                    for desc, qty, price, amount in v["items"]:
                        tx.execute("INSERT INTO INVOICE_ITEM (Item_ID, Invoice_ID, Description, Quantity, "
                                   "Unit_Price, Amount) VALUES (%s, %s, %s, %s, %s, %s)",
                                   (item_id, inv_id, desc, qty, str(price), str(amount)))
                        item_id += 1
                flash("Invoice %d created. Total %s." % (inv_id, money(total)), "ok")
                return redirect(url_for("invoice_detail", iid=inv_id))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("invoice_form.html", form=form, subs=subscriptions_for_select(), lines=range(1, 6))


@app.route("/invoices/<int:iid>")
def invoice_detail(iid):
    inv = invoice_summary(iid)
    if not inv:
        return not_found(None)
    inv["Balance"] = round(inv["Total_Amount"] - inv["Paid"], 2)
    items = db.query("SELECT Item_ID, Description, Quantity, Unit_Price, Amount FROM INVOICE_ITEM "
                     "WHERE Invoice_ID = %s ORDER BY Item_ID", (iid,))
    payments = db.query("SELECT p.Payment_ID, p.Payment_Date, p.Payment_Method, p.Amount_Paid, p.Status, "
                        "(SELECT COALESCE(SUM(r.Refund_Amount), 0) FROM REFUND r WHERE r.Payment_ID = p.Payment_ID) AS Refunded "
                        "FROM PAYMENT p WHERE p.Invoice_ID = %s ORDER BY p.Payment_Date, p.Payment_ID", (iid,))
    refunds = db.query("SELECT r.Refund_ID, r.Payment_ID, r.Refund_Date, r.Refund_Amount, r.Reason, r.Refund_Status "
                       "FROM REFUND r JOIN PAYMENT p ON p.Payment_ID = r.Payment_ID WHERE p.Invoice_ID = %s "
                       "ORDER BY r.Refund_ID", (iid,))
    return render_template("invoice_detail.html", inv=inv, items=items, payments=payments, refunds=refunds,
                           methods=val.PAYMENT_METHODS, pay_statuses=val.PAYMENT_STATUSES,
                           refund_statuses=val.REFUND_STATUSES, form={})


@app.route("/invoices/<int:iid>/pay", methods=["POST"])
def invoice_pay(iid):
    inv = invoice_summary(iid)
    if not inv:
        return not_found(None)
    balance = round(inv["Total_Amount"] - inv["Paid"], 2)
    v, errors = val.validate_payment(request.form, balance)
    if not errors:
        try:
            with db.transaction() as tx:          # payment row + invoice status change together
                pay_id = tx.next_id("PAYMENT")
                tx.execute("INSERT INTO PAYMENT (Payment_ID, Invoice_ID, Payment_Date, Payment_Method, Amount_Paid, Status) "
                           "VALUES (%s, %s, %s, %s, %s, %s)",
                           (pay_id, iid, v["date"].isoformat(), v["method"], str(v["amount"]), v["status"]))
                paid = tx.one("SELECT COALESCE(SUM(Amount_Paid), 0) AS n FROM PAYMENT "
                              "WHERE Invoice_ID = %s AND Status = 'Success'", (iid,))["n"]
                if round(paid, 2) >= round(inv["Total_Amount"], 2):
                    tx.execute("UPDATE INVOICE SET Invoice_Status = 'Paid' WHERE Invoice_ID = %s", (iid,))
            flash("Payment %d recorded." % pay_id, "ok")
        except db.DB_ERRORS as exc:
            flash(db.friendly_error(exc), "error")
    else:
        show_errors(errors)
    return redirect(url_for("invoice_detail", iid=iid))


@app.route("/payments/<int:pid>/refund", methods=["POST"])
def payment_refund(pid):
    pay = db.one("SELECT p.Payment_ID, p.Invoice_ID, p.Amount_Paid, p.Status, "
                 "(SELECT COALESCE(SUM(r.Refund_Amount), 0) FROM REFUND r WHERE r.Payment_ID = p.Payment_ID) AS Refunded "
                 "FROM PAYMENT p WHERE p.Payment_ID = %s", (pid,))
    if not pay:
        return not_found(None)
    if pay["Status"] != "Success":
        flash("Only a successful payment can be refunded.", "error")
        return redirect(url_for("invoice_detail", iid=pay["Invoice_ID"]))
    refundable = round(pay["Amount_Paid"] - pay["Refunded"], 2)
    v, errors = val.validate_refund(request.form, refundable)
    if not errors:
        try:
            with db.transaction() as tx:
                rid = tx.next_id("REFUND")
                tx.execute("INSERT INTO REFUND (Refund_ID, Payment_ID, Refund_Date, Refund_Amount, Reason, Refund_Status) "
                           "VALUES (%s, %s, %s, %s, %s, %s)",
                           (rid, pid, v["date"].isoformat(), str(v["amount"]), v["reason"] or None, v["status"]))
            flash("Refund %d recorded." % rid, "ok")
        except db.DB_ERRORS as exc:
            flash(db.friendly_error(exc), "error")
    else:
        show_errors(errors)
    return redirect(url_for("invoice_detail", iid=pay["Invoice_ID"]))


@app.route("/invoices/<int:iid>/delete", methods=["POST"])
def invoice_delete(iid):
    try:
        count = db.execute("DELETE FROM INVOICE WHERE Invoice_ID = %s", (iid,))   # items are removed by ON DELETE CASCADE
        flash("Invoice deleted." if count else "Invoice not found.", "ok" if count else "error")
        return redirect(url_for("invoices"))
    except db.DB_ERRORS:
        flash("This invoice cannot be deleted because payments exist for it.", "error")
        return redirect(url_for("invoice_detail", iid=iid))


# ------------------------------------------------------------------ tickets
@app.route("/tickets")
def tickets():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    sql = ("SELECT st.Ticket_ID, c.Company_Name, st.Issue_Type, st.Priority, st.Ticket_Status, st.Created_Date, "
           "st.Resolved_Date FROM SUPPORT_TICKET st JOIN CLIENT c ON c.Client_ID = st.Client_ID WHERE 1 = 1")
    params = []
    if q:
        sql += " AND c.Company_Name LIKE %s"
        params.append("%" + q + "%")
    if status in val.TICKET_STATUSES:
        sql += " AND st.Ticket_Status = %s"
        params.append(status)
    if priority in val.PRIORITIES:
        sql += " AND st.Priority = %s"
        params.append(priority)
    rows = db.query(sql + " ORDER BY st.Ticket_ID", params)
    return render_template("tickets.html", rows=rows, q=q, status=status, priority=priority,
                           statuses=val.TICKET_STATUSES, priorities=val.PRIORITIES)


def ticket_choices():
    return {"clients": clients_for_select(), "issues": val.ISSUE_TYPES, "priorities": val.PRIORITIES,
            "statuses": val.TICKET_STATUSES}


@app.route("/tickets/new", methods=["GET", "POST"])
def ticket_new():
    form = request.form if request.method == "POST" else {"created": today(), "status": "Open", "priority": "Medium"}
    if request.method == "POST":
        v, errors = val.validate_ticket(form)
        if not errors:
            resolved = v["created"].isoformat() if v["status"] == "Resolved" else None
            try:
                with db.transaction() as tx:
                    new_id = tx.next_id("SUPPORT_TICKET")
                    tx.execute("INSERT INTO SUPPORT_TICKET (Ticket_ID, Client_ID, Issue_Type, Priority, Ticket_Status, "
                               "Created_Date, Resolved_Date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                               (new_id, v["client"], v["issue"], v["priority"], v["status"],
                                v["created"].isoformat(), resolved))
                flash("Ticket %d raised." % new_id, "ok")
                return redirect(url_for("tickets"))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("ticket_form.html", form=form, mode="new", ticket_id=None, **ticket_choices())


@app.route("/tickets/<int:tid>/edit", methods=["GET", "POST"])
def ticket_edit(tid):
    t = db.one("SELECT * FROM SUPPORT_TICKET WHERE Ticket_ID = %s", (tid,))
    if not t:
        return not_found(None)
    form = request.form if request.method == "POST" else {
        "client": t["Client_ID"], "issue": t["Issue_Type"], "priority": t["Priority"],
        "status": t["Ticket_Status"], "created": t["Created_Date"]}
    if request.method == "POST":
        v, errors = val.validate_ticket(form)
        if not errors:
            resolved = None
            if v["status"] == "Resolved":           # keep old resolved date, else use today (but not before created)
                resolved = t["Resolved_Date"] or max(date.today(), v["created"]).isoformat()
            try:
                db.execute("UPDATE SUPPORT_TICKET SET Client_ID = %s, Issue_Type = %s, Priority = %s, Ticket_Status = %s, "
                           "Created_Date = %s, Resolved_Date = %s WHERE Ticket_ID = %s",
                           (v["client"], v["issue"], v["priority"], v["status"], v["created"].isoformat(), resolved, tid))
                flash("Ticket updated.", "ok")
                return redirect(url_for("tickets"))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("ticket_form.html", form=form, mode="edit", ticket_id=tid, **ticket_choices())


@app.route("/tickets/<int:tid>/delete", methods=["POST"])
def ticket_delete(tid):
    count = db.execute("DELETE FROM SUPPORT_TICKET WHERE Ticket_ID = %s", (tid,))
    flash("Ticket deleted." if count else "Ticket not found.", "ok" if count else "error")
    return redirect(url_for("tickets"))


# -------------------------------------------------------------------- usage
@app.route("/usage")
def usage():
    sub = val.as_int(request.args.get("sub", ""))
    sql = ("SELECT u.Usage_ID, u.Subscription_ID, c.Company_Name, t.Tier_Name, u.Usage_Date, u.Active_Users, t.Max_Users, "
           "u.Storage_Used_GB, t.Storage_GB, "
           "CASE WHEN u.Storage_Used_GB > t.Storage_GB OR u.Active_Users > t.Max_Users THEN 'Over limit' ELSE 'OK' END AS Flag "
           "FROM USAGE_RECORD u JOIN SUBSCRIPTION s ON s.Subscription_ID = u.Subscription_ID "
           "JOIN CLIENT c ON c.Client_ID = s.Client_ID JOIN PRICING_TIER t ON t.Tier_ID = s.Tier_ID WHERE 1 = 1")
    params = []
    if sub:
        sql += " AND u.Subscription_ID = %s"
        params.append(sub)
    rows = db.query(sql + " ORDER BY u.Usage_Date DESC, u.Usage_ID DESC", params)
    return render_template("usage.html", rows=rows, sub=sub, subs=subscriptions_for_select(False))


@app.route("/usage/new", methods=["GET", "POST"])
def usage_new():
    form = request.form if request.method == "POST" else {"date": today()}
    if request.method == "POST":
        v, errors = val.validate_usage(form)
        if not errors:
            try:
                with db.transaction() as tx:
                    new_id = tx.next_id("USAGE_RECORD")
                    tx.execute("INSERT INTO USAGE_RECORD (Usage_ID, Subscription_ID, Active_Users, Storage_Used_GB, Usage_Date) "
                               "VALUES (%s, %s, %s, %s, %s)",
                               (new_id, v["subscription"], v["users"], str(v["storage"]), v["date"].isoformat()))
                flash("Usage record added.", "ok")
                return redirect(url_for("usage"))
            except db.DB_ERRORS as exc:
                errors["db"] = db.friendly_error(exc)
        show_errors(errors)
    return render_template("usage_form.html", form=form, subs=subscriptions_for_select())


# ------------------------------------------------------------------ reports
REPORTS = [
    ("Revenue by pricing tier", "View + GROUP BY",
     "SELECT Tier_Name, Subscriptions, Revenue\nFROM vw_tier_revenue\nORDER BY Revenue DESC"),
    ("Invoices with an outstanding balance", "View + WHERE + ORDER BY",
     "SELECT Invoice_ID, Company_Name, Total_Amount, Amount_Paid, Balance, Invoice_Status\n"
     "FROM vw_invoice_balance\nWHERE Balance > 0\nORDER BY Due_Date, Invoice_ID"),
    ("Clients holding more than one subscription", "JOIN + GROUP BY + HAVING",
     "SELECT c.Company_Name, COUNT(*) AS Subscriptions\nFROM CLIENT c\n"
     "JOIN SUBSCRIPTION s ON s.Client_ID = c.Client_ID\nGROUP BY c.Company_Name\n"
     "HAVING COUNT(*) > 1\nORDER BY c.Company_Name"),
    ("Clients with at least one overdue invoice", "Subquery (IN)",
     "SELECT Client_ID, Company_Name\nFROM CLIENT\nWHERE Client_ID IN (\n"
     "    SELECT s.Client_ID\n    FROM SUBSCRIPTION s\n"
     "    JOIN INVOICE i ON i.Subscription_ID = s.Subscription_ID\n"
     "    WHERE i.Invoice_Status = 'Overdue')\nORDER BY Client_ID"),
    ("Usage that crossed the plan storage limit", "Correlated subquery",
     "SELECT u.Subscription_ID, u.Usage_Date, u.Storage_Used_GB\nFROM USAGE_RECORD u\n"
     "JOIN SUBSCRIPTION s ON s.Subscription_ID = u.Subscription_ID\n"
     "WHERE u.Storage_Used_GB > (SELECT t.Storage_GB\n"
     "                           FROM PRICING_TIER t\n"
     "                           WHERE t.Tier_ID = s.Tier_ID)\nORDER BY u.Subscription_ID, u.Usage_Date"),
    ("Invoices larger than the average invoice", "Scalar subquery",
     "SELECT Invoice_ID, Subscription_ID, Total_Amount\nFROM INVOICE\n"
     "WHERE Total_Amount > (SELECT AVG(Total_Amount) FROM INVOICE)\nORDER BY Total_Amount DESC, Invoice_ID"),
    ("Support tickets per client (including clients with none)", "LEFT JOIN + GROUP BY",
     "SELECT c.Company_Name, COUNT(st.Ticket_ID) AS Tickets\nFROM CLIENT c\n"
     "LEFT JOIN SUPPORT_TICKET st ON st.Client_ID = c.Client_ID\nGROUP BY c.Company_Name\n"
     "ORDER BY Tickets DESC, c.Company_Name"),
]


@app.route("/reports")
def reports():
    results = []
    for title, concept, sql in REPORTS:
        rows = db.query(sql)
        results.append({"title": title, "concept": concept, "sql": sql, "rows": rows,
                        "cols": list(rows[0].keys()) if rows else []})
    return render_template("reports.html", results=results)


if __name__ == "__main__":
    import threading
    import webbrowser
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000/")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)     # only this computer can open the site
