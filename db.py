import os
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

    return connection









''' Why this file (db.py) separated?

👉 Keeps database logic separate
👉 Reusable across all modules
👉 Clean architecture (very important later) '''








'''
Database Query:
CREATE DATABASE shop_management;

USE shop_management;

-- 1. USERS (Authentication)
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);

ALTER TABLE users ADD role VARCHAR(20) DEFAULT 'staff';

SELECT * FROM users;


-- 2. CATEGORIES
CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- 3. SUPPLIERS
CREATE TABLE suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20)
);

-- 4. CUSTOMERS
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20)
);

-- 5. PRODUCTS
CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category_id INT,
    supplier_id INT,
    buying_price DECIMAL(10,2),
    extra_cost DECIMAL(10,2),
    selling_price DECIMAL(10,2) NOT NULL,
    quantity INT DEFAULT 0,

    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);
/* Note:
quantity = current stock (updated by transactions)
cost fields = for profit calculation later */


-- 6. PURCHASES
CREATE TABLE purchases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id INT NOT NULL,
    total_amount DECIMAL(10,2),
    is_credit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

-- 7. PURCHASE_ITEMS
CREATE TABLE purchase_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    purchase_id INT,
    product_id INT,
    quantity INT NOT NULL,
    unit_cost DECIMAL(10,2) NOT NULL,

    FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
-- 👉 ON DELETE CASCADE = if purchase deleted → its items deleted automatically


-- 8. PAYABLES
CREATE TABLE payables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id INT,
    purchase_id INT,
    amount_due DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (purchase_id) REFERENCES purchases(id)
);

-- 9. PAYABLE PAYMENTS
CREATE TABLE payable_payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    payable_id INT,
    amount_paid DECIMAL(10,2),
    payment_link VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (payable_id) REFERENCES payables(id) ON DELETE CASCADE
);

-- 10. SALES
CREATE TABLE sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    total_amount DECIMAL(10,2),
    is_credit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

-- 11. SALE_ITEMS
CREATE TABLE sale_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT,
    product_id INT,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,

    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- 12. RECEIVABLES
CREATE TABLE receivables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    sale_id INT,
    amount_due DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (sale_id) REFERENCES sales(id)
);

-- 13. RECEIVABLE PAYMENTS
CREATE TABLE receivable_payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    receivable_id INT,
    amount_paid DECIMAL(10,2),
    payment_link VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (receivable_id) REFERENCES receivables(id) ON DELETE CASCADE
);

-- Check all tables if registered
SHOW TABLES;

-- Check the detailed structure of the product table
DESCRIBE products;

--  የሚለው ትእዛዝ purchase_items የተባለውን ሰንጠረዥ (Table) ለመፍጠር የሚያስፈልገውን ሙሉ የSQL ኮድ ያወጣል።
SHOW CREATE TABLE purchase_items;

-- checking the tables correctness
INSERT INTO categories (name) VALUES ('Clothes');

INSERT INTO suppliers (name, phone)
VALUES ('Supplier A', '0912345678');

INSERT INTO products (name, category_id, supplier_id, selling_price, quantity)
VALUES ('T-Shirt', 1, 1, 200, 10);

SELECT * FROM products;



'''