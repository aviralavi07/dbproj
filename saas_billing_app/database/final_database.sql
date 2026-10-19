-- =====================================================================
-- Cloud SaaS Subscription and Billing Management System
-- FINAL DATABASE (Review 3)  -  MySQL 8.0
-- Aviral Srivastava (25BCE2019), Somil Krishnani (25BCE2007), Parth Sikka (25BDS0109)
--
-- How to use:   mysql -u root -p < final_database.sql
-- The script is safe to run again: it rebuilds the database from scratch.
-- It is the same schema and sample data as Review 2, with the three views.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS saas_billing_db;
USE saas_billing_db;

DROP VIEW IF EXISTS vw_tier_revenue;
DROP VIEW IF EXISTS vw_invoice_balance;
DROP VIEW IF EXISTS vw_active_subscriptions;
DROP TABLE IF EXISTS REFUND;
DROP TABLE IF EXISTS PAYMENT;
DROP TABLE IF EXISTS INVOICE_ITEM;
DROP TABLE IF EXISTS INVOICE;
DROP TABLE IF EXISTS USAGE_RECORD;
DROP TABLE IF EXISTS CANCELLATION;
DROP TABLE IF EXISTS SUPPORT_TICKET;
DROP TABLE IF EXISTS SUBSCRIPTION;
DROP TABLE IF EXISTS PRICING_TIER;
DROP TABLE IF EXISTS CLIENT;

-- ------------------------- Tables -------------------------
CREATE TABLE CLIENT (
    Client_ID       INT PRIMARY KEY,
    Company_Name    VARCHAR(100) NOT NULL,
    Contact_Person  VARCHAR(80)  NOT NULL,
    Email           VARCHAR(100) NOT NULL UNIQUE,
    Phone           VARCHAR(15),
    Signup_Date     DATE NOT NULL,
    Auto_Renew      BOOLEAN NOT NULL DEFAULT 1
        CHECK (Auto_Renew IN (0, 1))
);

CREATE TABLE PRICING_TIER (
    Tier_ID       INT PRIMARY KEY,
    Tier_Name     VARCHAR(50) NOT NULL UNIQUE,
    Monthly_Rate  DECIMAL(10,2) NOT NULL
        CHECK (Monthly_Rate > 0),
    Max_Users     INT NOT NULL CHECK (Max_Users > 0),
    Storage_GB    INT NOT NULL CHECK (Storage_GB > 0)
);

CREATE TABLE SUBSCRIPTION (
    Subscription_ID  INT PRIMARY KEY,
    Client_ID        INT NOT NULL,
    Tier_ID          INT NOT NULL,
    Start_Date       DATE NOT NULL,
    End_Date         DATE,
    Status           VARCHAR(20) NOT NULL
        DEFAULT 'Active'
                     CHECK (Status IN ('Active',
                         'Expired', 'Cancelled')),
    CHECK (End_Date IS NULL OR End_Date >= Start_Date),
    FOREIGN KEY (Client_ID)
        REFERENCES CLIENT (Client_ID),
    FOREIGN KEY (Tier_ID)
        REFERENCES PRICING_TIER (Tier_ID)
);

CREATE TABLE CANCELLATION (
    Cancellation_ID  INT PRIMARY KEY,
    Subscription_ID  INT NOT NULL UNIQUE,
    Request_Date     DATE NOT NULL,
    Effective_Date   DATE NOT NULL,
    Reason           VARCHAR(150),
    CHECK (Effective_Date >= Request_Date),
    FOREIGN KEY (Subscription_ID)
        REFERENCES SUBSCRIPTION (Subscription_ID)
);

CREATE TABLE SUPPORT_TICKET (
    Ticket_ID      INT PRIMARY KEY,
    Client_ID      INT NOT NULL,
    Issue_Type     VARCHAR(50) NOT NULL
        CHECK (Issue_Type IN ('Billing', 'Technical',
        'Account')),
    Priority       VARCHAR(10) NOT NULL CHECK (Priority
        IN ('Low', 'Medium', 'High')),
    Ticket_Status  VARCHAR(20) NOT NULL DEFAULT 'Open'
                   CHECK (Ticket_Status IN ('Open',
                       'In Progress', 'Resolved')),
    Created_Date   DATE NOT NULL,
    Resolved_Date  DATE,
    CHECK (Resolved_Date IS NULL
        OR Resolved_Date >= Created_Date),
    FOREIGN KEY (Client_ID)
        REFERENCES CLIENT (Client_ID)
);

CREATE TABLE INVOICE (
    Invoice_ID       INT PRIMARY KEY,
    Subscription_ID  INT NOT NULL,
    Invoice_Date     DATE NOT NULL,
    Due_Date         DATE NOT NULL,
    Total_Amount     DECIMAL(12,2) NOT NULL
        CHECK (Total_Amount >= 0),
    Invoice_Status   VARCHAR(20) NOT NULL
        DEFAULT 'Pending'
                     CHECK (Invoice_Status IN ('Pending',
                         'Paid', 'Overdue')),
    CHECK (Due_Date >= Invoice_Date),
    FOREIGN KEY (Subscription_ID)
        REFERENCES SUBSCRIPTION (Subscription_ID)
);

CREATE TABLE INVOICE_ITEM (
    Item_ID     INT PRIMARY KEY,
    Invoice_ID  INT NOT NULL,
    Description VARCHAR(150) NOT NULL,
    Quantity    INT NOT NULL CHECK (Quantity > 0),
    Unit_Price  DECIMAL(10,2) NOT NULL
        CHECK (Unit_Price >= 0),
    Amount      DECIMAL(12,2) NOT NULL
        CHECK (Amount >= 0),
    FOREIGN KEY (Invoice_ID)
        REFERENCES INVOICE (Invoice_ID)
        ON DELETE CASCADE
);

CREATE TABLE PAYMENT (
    Payment_ID      INT PRIMARY KEY,
    Invoice_ID      INT NOT NULL,
    Payment_Date    DATE NOT NULL,
    Payment_Method  VARCHAR(30) NOT NULL
                    CHECK (Payment_Method IN ('Card',
                        'UPI', 'Net Banking',
                        'Bank Transfer')),
    Amount_Paid     DECIMAL(12,2) NOT NULL
        CHECK (Amount_Paid > 0),
    Status          VARCHAR(20) NOT NULL CHECK (Status
        IN ('Success', 'Failed', 'Pending')),
    FOREIGN KEY (Invoice_ID)
        REFERENCES INVOICE (Invoice_ID)
);

CREATE TABLE REFUND (
    Refund_ID      INT PRIMARY KEY,
    Payment_ID     INT NOT NULL,
    Refund_Date    DATE NOT NULL,
    Refund_Amount  DECIMAL(12,2) NOT NULL
        CHECK (Refund_Amount > 0),
    Reason         VARCHAR(150),
    Refund_Status  VARCHAR(20) NOT NULL
        CHECK (Refund_Status IN ('Requested', 'Approved',
        'Processed')),
    FOREIGN KEY (Payment_ID)
        REFERENCES PAYMENT (Payment_ID)
);

CREATE TABLE USAGE_RECORD (
    Usage_ID         INT PRIMARY KEY,
    Subscription_ID  INT NOT NULL,
    Active_Users     INT NOT NULL
        CHECK (Active_Users >= 0),
    Storage_Used_GB  DECIMAL(10,2) NOT NULL
        CHECK (Storage_Used_GB >= 0),
    Usage_Date       DATE NOT NULL,
    FOREIGN KEY (Subscription_ID)
        REFERENCES SUBSCRIPTION (Subscription_ID)
);

-- ------------------------- Sample data -------------------------
INSERT INTO PRICING_TIER (Tier_ID, Tier_Name, Monthly_Rate, Max_Users, Storage_GB) VALUES
    (1, 'Starter', 1999.0, 10, 50),
    (2, 'Growth', 4999.0, 50, 200),
    (3, 'Business', 9999.0, 150, 500),
    (4, 'Enterprise', 24999.0, 500, 2000);
INSERT INTO CLIENT (Client_ID, Company_Name, Contact_Person, Email, Phone, Signup_Date, Auto_Renew) VALUES
    (1, 'Nexora Technologies', 'Ravi Menon', 'ravi.menon@nexora.example', '9840011223', '2025-11-12', 1),
    (2, 'BlueLeaf Logistics', 'Priya Nair', 'priya.nair@blueleaf.example', '9884455667', '2025-12-03', 1),
    (3, 'Sundaram Textiles', 'Karthik Subramanian', 'karthik.s@sundaramtex.example', '9443322110', '2026-01-18', 0),
    (4, 'Apex Health Labs', 'Meera Iyer', 'meera.iyer@apexhealth.example', '9962200431', '2025-10-25', 1),
    (5, 'CodeCraft Studios', 'Arjun Reddy', 'arjun@codecraft.example', '9705566778', '2026-02-09', 1),
    (6, 'GreenGrid Energy', 'Sneha Kulkarni', 'sneha.k@greengrid.example', '9820098765', '2026-01-02', 0),
    (7, 'UrbanNest Realty', 'Imran Khan', 'imran.khan@urbannest.example', '9811122334', '2026-03-14', 1),
    (8, 'EduSpark Learning', 'Divya Rajan', 'divya.rajan@eduspark.example', '9790033445', '2025-09-15', 0),
    (9, 'FreshBasket Foods', 'Rohit Sharma', 'rohit.sharma@freshbasket.example', '9899900112', '2026-02-27', 1),
    (10, 'Orbit Analytics', 'Ananya Das', 'ananya.das@orbit.example', '9830044556', '2026-06-20', 1);
INSERT INTO SUBSCRIPTION (Subscription_ID, Client_ID, Tier_ID, Start_Date, End_Date, Status) VALUES
    (1, 1, 2, '2026-01-05', NULL, 'Active'),
    (2, 2, 3, '2026-02-10', NULL, 'Active'),
    (3, 3, 1, '2026-03-01', NULL, 'Active'),
    (4, 4, 4, '2026-01-15', NULL, 'Active'),
    (5, 5, 2, '2026-04-01', '2026-08-31', 'Cancelled'),
    (6, 6, 1, '2026-02-20', NULL, 'Active'),
    (7, 7, 3, '2026-05-01', NULL, 'Active'),
    (8, 8, 2, '2025-10-01', '2026-03-31', 'Expired'),
    (9, 1, 1, '2026-06-01', NULL, 'Active'),
    (10, 9, 3, '2026-03-15', '2026-09-15', 'Cancelled'),
    (11, 10, 2, '2026-07-01', NULL, 'Active'),
    (12, 4, 3, '2026-06-10', NULL, 'Active');
INSERT INTO CANCELLATION (Cancellation_ID, Subscription_ID, Request_Date, Effective_Date, Reason) VALUES
    (1, 5, '2026-08-10', '2026-08-31', 'Moving to an in-house tool'),
    (2, 10, '2026-09-01', '2026-09-15', 'Budget cuts');
INSERT INTO SUPPORT_TICKET (Ticket_ID, Client_ID, Issue_Type, Priority, Ticket_Status, Created_Date, Resolved_Date) VALUES
    (1, 1, 'Billing', 'Medium', 'Resolved', '2026-08-05', '2026-08-06'),
    (2, 2, 'Technical', 'High', 'Resolved', '2026-08-12', '2026-08-14'),
    (3, 3, 'Billing', 'Low', 'Open', '2026-09-22', NULL),
    (4, 4, 'Technical', 'High', 'In Progress', '2026-09-25', NULL),
    (5, 5, 'Account', 'Medium', 'Resolved', '2026-08-08', '2026-08-09'),
    (6, 6, 'Billing', 'High', 'Open', '2026-09-28', NULL),
    (7, 7, 'Technical', 'Medium', 'Resolved', '2026-09-03', '2026-09-05'),
    (8, 1, 'Technical', 'Low', 'Resolved', '2026-09-10', '2026-09-12'),
    (9, 9, 'Billing', 'Medium', 'Resolved', '2026-08-30', '2026-09-01'),
    (10, 10, 'Account', 'Low', 'Open', '2026-09-30', NULL);
INSERT INTO INVOICE (Invoice_ID, Subscription_ID, Invoice_Date, Due_Date, Total_Amount, Invoice_Status) VALUES
    (1, 1, '2026-08-01', '2026-08-15', 5749.0, 'Paid'),
    (2, 2, '2026-08-01', '2026-08-15', 11499.0, 'Paid'),
    (3, 3, '2026-08-01', '2026-08-15', 1999.0, 'Overdue'),
    (4, 4, '2026-08-01', '2026-08-15', 27249.0, 'Paid'),
    (5, 5, '2026-08-01', '2026-08-15', 4999.0, 'Paid'),
    (6, 6, '2026-08-01', '2026-08-15', 1999.0, 'Paid'),
    (7, 7, '2026-08-01', '2026-08-15', 9999.0, 'Overdue'),
    (8, 9, '2026-08-01', '2026-08-15', 1999.0, 'Paid'),
    (9, 10, '2026-08-01', '2026-08-15', 9999.0, 'Overdue'),
    (10, 11, '2026-08-01', '2026-08-15', 4999.0, 'Paid'),
    (11, 12, '2026-08-01', '2026-08-15', 10599.0, 'Paid'),
    (12, 1, '2026-09-20', '2026-10-05', 4999.0, 'Paid'),
    (13, 2, '2026-09-20', '2026-10-05', 11199.0, 'Paid'),
    (14, 3, '2026-09-20', '2026-10-05', 2599.0, 'Pending'),
    (15, 4, '2026-09-20', '2026-10-05', 24999.0, 'Paid'),
    (16, 6, '2026-09-20', '2026-10-05', 1999.0, 'Pending'),
    (17, 7, '2026-09-20', '2026-10-05', 10749.0, 'Pending'),
    (18, 9, '2026-09-20', '2026-10-05', 1999.0, 'Pending'),
    (19, 11, '2026-09-20', '2026-10-05', 5749.0, 'Pending'),
    (20, 12, '2026-09-20', '2026-10-05', 9999.0, 'Paid');
INSERT INTO INVOICE_ITEM (Item_ID, Invoice_ID, Description, Quantity, Unit_Price, Amount) VALUES
    (1, 1, 'Monthly plan fee - Growth', 1, 4999.0, 4999.0),
    (2, 1, 'Extra storage (100 GB)', 1, 750.0, 750.0),
    (3, 2, 'Monthly plan fee - Business', 1, 9999.0, 9999.0),
    (4, 2, 'Extra storage (100 GB)', 2, 750.0, 1500.0),
    (5, 3, 'Monthly plan fee - Starter', 1, 1999.0, 1999.0),
    (6, 4, 'Monthly plan fee - Enterprise', 1, 24999.0, 24999.0),
    (7, 4, 'Extra storage (100 GB)', 3, 750.0, 2250.0),
    (8, 5, 'Monthly plan fee - Growth', 1, 4999.0, 4999.0),
    (9, 6, 'Monthly plan fee - Starter', 1, 1999.0, 1999.0),
    (10, 7, 'Monthly plan fee - Business', 1, 9999.0, 9999.0),
    (11, 8, 'Monthly plan fee - Starter', 1, 1999.0, 1999.0),
    (12, 9, 'Monthly plan fee - Business', 1, 9999.0, 9999.0),
    (13, 10, 'Monthly plan fee - Growth', 1, 4999.0, 4999.0),
    (14, 11, 'Monthly plan fee - Business', 1, 9999.0, 9999.0),
    (15, 11, 'Extra users (10 users)', 1, 600.0, 600.0),
    (16, 12, 'Monthly plan fee - Growth', 1, 4999.0, 4999.0),
    (17, 13, 'Monthly plan fee - Business', 1, 9999.0, 9999.0),
    (18, 13, 'Extra users (10 users)', 2, 600.0, 1200.0),
    (19, 14, 'Monthly plan fee - Starter', 1, 1999.0, 1999.0),
    (20, 14, 'Extra users (10 users)', 1, 600.0, 600.0),
    (21, 15, 'Monthly plan fee - Enterprise', 1, 24999.0, 24999.0),
    (22, 16, 'Monthly plan fee - Starter', 1, 1999.0, 1999.0),
    (23, 17, 'Monthly plan fee - Business', 1, 9999.0, 9999.0),
    (24, 17, 'Extra storage (100 GB)', 1, 750.0, 750.0),
    (25, 18, 'Monthly plan fee - Starter', 1, 1999.0, 1999.0),
    (26, 19, 'Monthly plan fee - Growth', 1, 4999.0, 4999.0),
    (27, 19, 'Extra storage (100 GB)', 1, 750.0, 750.0),
    (28, 20, 'Monthly plan fee - Business', 1, 9999.0, 9999.0);
INSERT INTO PAYMENT (Payment_ID, Invoice_ID, Payment_Date, Payment_Method, Amount_Paid, Status) VALUES
    (1, 1, '2026-08-05', 'Card', 5749.0, 'Success'),
    (2, 2, '2026-08-06', 'Net Banking', 11499.0, 'Success'),
    (3, 4, '2026-08-08', 'Bank Transfer', 16349.4, 'Success'),
    (4, 4, '2026-08-14', 'Bank Transfer', 10899.6, 'Success'),
    (5, 5, '2026-08-09', 'Card', 4999.0, 'Success'),
    (6, 6, '2026-08-10', 'Card', 1999.0, 'Failed'),
    (7, 6, '2026-08-11', 'Net Banking', 1999.0, 'Success'),
    (8, 8, '2026-08-05', 'UPI', 1999.0, 'Success'),
    (9, 10, '2026-08-07', 'Net Banking', 4999.0, 'Success'),
    (10, 11, '2026-08-08', 'Bank Transfer', 10599.0, 'Success'),
    (11, 12, '2026-09-28', 'Card', 4999.0, 'Failed'),
    (12, 12, '2026-09-29', 'UPI', 4999.0, 'Success'),
    (13, 13, '2026-09-29', 'Card', 11199.0, 'Success'),
    (14, 15, '2026-09-24', 'Bank Transfer', 24999.0, 'Success'),
    (15, 19, '2026-09-28', 'UPI', 5749.0, 'Pending'),
    (16, 20, '2026-09-29', 'UPI', 9999.0, 'Success');
INSERT INTO REFUND (Refund_ID, Payment_ID, Refund_Date, Refund_Amount, Reason, Refund_Status) VALUES
    (1, 5, '2026-09-05', 2499.5, 'Pro-rata refund on cancellation', 'Processed'),
    (2, 2, '2026-08-25', 750.0, 'Overcharged for extra storage', 'Processed'),
    (3, 16, '2026-09-29', 2000.0, 'Service downtime credit', 'Requested');
INSERT INTO USAGE_RECORD (Usage_ID, Subscription_ID, Active_Users, Storage_Used_GB, Usage_Date) VALUES
    (1, 1, 31, 124.0, '2026-08-31'),
    (2, 2, 72, 240.0, '2026-08-31'),
    (3, 3, 9, 45.0, '2026-08-31'),
    (4, 4, 275, 1100.0, '2026-08-31'),
    (5, 5, 25, 100.0, '2026-08-31'),
    (6, 6, 8, 40.0, '2026-08-31'),
    (7, 7, 60, 200.0, '2026-08-31'),
    (8, 9, 7, 35.0, '2026-08-31'),
    (9, 10, 68, 225.0, '2026-08-31'),
    (10, 11, 16, 66.0, '2026-08-31'),
    (11, 12, 87, 290.0, '2026-08-31'),
    (12, 1, 28, 110.0, '2026-09-30'),
    (13, 2, 106, 355.0, '2026-09-30'),
    (14, 3, 10, 48.0, '2026-09-30'),
    (15, 4, 305, 1220.0, '2026-09-30'),
    (16, 6, 10, 52.4, '2026-09-30'),
    (17, 7, 68, 225.0, '2026-09-30'),
    (18, 9, 8, 39.0, '2026-09-30'),
    (19, 11, 26, 104.0, '2026-09-30'),
    (20, 12, 96, 320.0, '2026-09-30');

-- ------------------------- Views -------------------------
CREATE OR REPLACE VIEW vw_active_subscriptions AS
SELECT s.Subscription_ID, c.Company_Name, t.Tier_Name,
    t.Monthly_Rate, s.Start_Date
FROM SUBSCRIPTION s
JOIN CLIENT c       ON c.Client_ID = s.Client_ID
JOIN PRICING_TIER t ON t.Tier_ID   = s.Tier_ID
WHERE s.Status = 'Active';

CREATE OR REPLACE VIEW vw_invoice_balance AS
SELECT i.Invoice_ID, c.Company_Name, i.Due_Date,
    i.Total_Amount,
       COALESCE(SUM(CASE WHEN p.Status = 'Success'
           THEN p.Amount_Paid END), 0) AS Amount_Paid,
       i.Total_Amount - COALESCE(SUM(CASE WHEN p.Status = 'Success' THEN p.Amount_Paid END), 0) AS Balance,
       i.Invoice_Status
FROM INVOICE i
JOIN SUBSCRIPTION s
    ON s.Subscription_ID = i.Subscription_ID
JOIN CLIENT c       ON c.Client_ID = s.Client_ID
LEFT JOIN PAYMENT p ON p.Invoice_ID = i.Invoice_ID
GROUP BY i.Invoice_ID, c.Company_Name, i.Due_Date,
    i.Total_Amount, i.Invoice_Status;

CREATE OR REPLACE VIEW vw_tier_revenue AS
SELECT t.Tier_Name, COUNT(DISTINCT s.Subscription_ID)
    AS Subscriptions,
       SUM(p.Amount_Paid) AS Revenue
FROM PRICING_TIER t
JOIN SUBSCRIPTION s ON s.Tier_ID = t.Tier_ID
JOIN INVOICE i
    ON i.Subscription_ID = s.Subscription_ID
JOIN PAYMENT p      ON p.Invoice_ID = i.Invoice_ID
WHERE p.Status = 'Success'
GROUP BY t.Tier_Name;
