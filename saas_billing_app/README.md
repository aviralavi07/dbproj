# Cloud SaaS Subscription and Billing Management System

A website that presents the project and contains the working application.
It runs on your own computer (localhost) and uses a MySQL 8 database.

Team: Aviral Srivastava (25BCE2019), Somil Krishnani (25BCE2007), Parth Sikka (25BDS0109)

## Pages
* Overview, Database design, Testing, Team: the project presentation
* Application: Dashboard, Clients, Plans, Subscriptions, Invoices, Support, Usage, Reports
* Privacy Policy and Terms and Conditions (links in the footer of every page)

## 1. Requirements
* Python 3.10 or newer
* MySQL Server 8.0

## 2. Create the database (once)
Open a terminal in this folder and run (enter your MySQL root password when asked):

    mysql -u root -p < database/final_database.sql

If the `mysql` command is not recognised, open `database/final_database.sql` in MySQL Workbench and run the whole script.
Running it again resets the data to the sample data.

## 3. Install and configure (once)
    pip install -r requirements.txt

Open `config.py` and put your MySQL password in `MYSQL_PASSWORD`.

## 4. Start the website
* Windows: double-click `start.bat`
* Mac or Linux: run `./start.sh`
* Or in a terminal: `python app.py`

The browser opens http://127.0.0.1:5000 by itself. The site accepts connections from this computer only.

## 5. Run the automatic tests
    python run_tests.py

57 application test cases (TC01 to TC57) and 18 website checks (SC01 to SC18). All should show PASS.
The tests use a temporary SQLite copy of the final database, so your MySQL data is not touched.

## 6. Backup
    mysqldump -u root -p saas_billing_db > backup_saas_billing_db.sql

## Folder structure
    app.py            routes and business rules
    content.py        fixed text and tables of the presentation pages
    db.py             database connection, transactions, error messages
    validators.py     input validation rules
    config.py         database settings
    templates/        HTML pages           static/   style sheet, favicon, images
    database/final_database.sql   final database (tables + data + views)
    tests/            test_app.py (57 test cases), test_site.py (18 website checks)
    LAUNCH_CHECKLIST.md           what must be done before the site is put on the internet
