"""Configuration for the Cloud SaaS Subscription and Billing Management System.

Change the MySQL values below (or set the environment variables) to match your computer.
"""
import os

# "mysql" is the real database used for the project.
# "sqlite" is only a fallback used for automatic tests and offline screenshots.
DB_ENGINE = os.getenv("DB_ENGINE", "mysql")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "AvsAvi@1312")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "saas_billing_db")

SQLITE_PATH = os.getenv("SQLITE_PATH", "saas_billing_test.db")

SECRET_KEY = os.getenv("SECRET_KEY", "saas-billing-review3-secret")
