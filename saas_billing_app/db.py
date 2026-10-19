"""Database connectivity layer.

All SQL in the application is written with %s placeholders (parameterised queries),
so user input is never pasted into the SQL text. This protects against SQL injection.
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import config

_mysql = None
if config.DB_ENGINE == "mysql":
    try:
        import mysql.connector as _mysql
    except ImportError:          # connector not installed
        _mysql = None

# exceptions raised by the database driver
DB_ERRORS = (_mysql.Error,) if _mysql is not None else (sqlite3.Error,)

ID_COLUMNS = {                    # table -> primary key (used by next_id)
    "CLIENT": "Client_ID", "PRICING_TIER": "Tier_ID", "SUBSCRIPTION": "Subscription_ID",
    "CANCELLATION": "Cancellation_ID", "SUPPORT_TICKET": "Ticket_ID", "INVOICE": "Invoice_ID",
    "INVOICE_ITEM": "Item_ID", "PAYMENT": "Payment_ID", "REFUND": "Refund_ID",
    "USAGE_RECORD": "Usage_ID",
}


def connect():
    """Open a new connection to the configured database."""
    if config.DB_ENGINE == "sqlite":
        con = sqlite3.connect(config.SQLITE_PATH)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con
    if _mysql is None:
        raise RuntimeError("MySQL driver missing. Install it with:  pip install mysql-connector-python")
    return _mysql.connect(host=config.MYSQL_HOST, port=config.MYSQL_PORT, user=config.MYSQL_USER,
                          password=config.MYSQL_PASSWORD, database=config.MYSQL_DATABASE)


def _clean(value):
    """Convert database types into simple Python types for the templates."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return value


class Tx:
    """A connection wrapper with query() and execute() helpers."""

    def __init__(self, con):
        self.con = con

    def _sql(self, sql):
        return sql.replace("%s", "?") if config.DB_ENGINE == "sqlite" else sql

    def query(self, sql, params=()):
        cur = self.con.cursor(dictionary=True) if config.DB_ENGINE == "mysql" else self.con.cursor()
        cur.execute(self._sql(sql), tuple(params))
        rows = cur.fetchall()
        cur.close()
        return [{k: _clean(v) for k, v in dict(r).items()} for r in rows]

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql, params=()):
        cur = self.con.cursor()
        cur.execute(self._sql(sql), tuple(params))
        count = cur.rowcount
        cur.close()
        return count

    def next_id(self, table):
        """Next primary key value (our tables use plain INT keys, as in Review 2)."""
        col = ID_COLUMNS[table]
        row = self.one("SELECT COALESCE(MAX(%s), 0) + 1 AS n FROM %s" % (col, table))
        return int(row["n"])


def query(sql, params=()):
    con = connect()
    try:
        return Tx(con).query(sql, params)
    finally:
        con.close()


def one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


@contextmanager
def transaction():
    """Run several statements as one unit: commit if all succeed, rollback if any fails."""
    con = connect()
    try:
        yield Tx(con)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def execute(sql, params=()):
    """Run one INSERT / UPDATE / DELETE as its own committed transaction. Returns rows affected."""
    with transaction() as tx:
        return tx.execute(sql, params)


def friendly_error(exc):
    """Turn a raw database error into a message a user can understand."""
    errno = getattr(exc, "errno", None)
    text = str(exc)
    if errno == 1062 or "UNIQUE constraint failed" in text:
        return "A record with the same unique value (for example e-mail or plan name) already exists."
    if errno == 1451:
        return "This record cannot be deleted because other records depend on it."
    if errno == 1452:
        return "The selected related record does not exist."
    if errno == 3819 or "CHECK constraint failed" in text:
        return "A value is outside the allowed range or list (CHECK constraint)."
    if "FOREIGN KEY constraint failed" in text:
        return "Operation blocked: related records exist or are missing (FOREIGN KEY constraint)."
    return "Database error: " + text
