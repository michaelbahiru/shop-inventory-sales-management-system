from flask import Flask, render_template, request, redirect, session, url_for
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")



@app.route('/')
def home():
    if 'user_id' in session:
        return redirect('/portal')
    return redirect('/login')




'''REGISTER STAFF ROUTE'''
@app.route('/register', methods=['GET', 'POST'])
def register():

    # 🔒 ONLY ADMIN CAN ACCESS
    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') != 'admin':
        return redirect('/unauthorized')

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # 🔐 HASH PASSWORD
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            # 🔴 CHECK IF USERNAME EXISTS
            cursor.execute(
                "SELECT id FROM users WHERE username=%s",
                (username,)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                conn.close()
                return "Username already exists"

            # 🔵 INSERT USER !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            cursor.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
            """, (
                username,
                hashed_password,
                role
            ))

            conn.commit()
            conn.close()

            return redirect('/portal')

        except Exception as e:

            conn.rollback()
            conn.close()

            return f"ERROR: {str(e)}"

    return render_template('register.html')





'''LOGIN ROUTE'''
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=%s",
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[2], password):

            # ✅ STORE SESSION
            session['user_id'] = user[0]
            session['role'] = user[3]

            # 🔥 ROLE-BASED REDIRECT
            if user[3] == 'admin':
                return redirect('/portal')

            elif user[3] == 'Sales':
                return redirect('/sales')

            elif user[3] == 'purchaser':
                return redirect('/inventory')

            else:
                return "Invalid role assigned"

        return "Invalid username or password"

    return render_template('login.html')




'''STEP 5 — PORTAL PAGE'''
@app.route('/portal')
def portal():
    if 'user_id' not in session:
        return redirect('/login')
    # -------------------------------------------
    if session.get('role') != 'admin':
        return redirect('/unauthorized')
    #--------------------------------------------
    return render_template('portal.html')


'''LOGOUT ROUTE'''
@app.route('/logout')
def logout():

    # 🔴 CLEAR SESSION
    session.clear()

    # 🔵 RETURN TO LOGIN
    return redirect('/login')



'''UNAUTHORIZED ROUTE'''
@app.route('/unauthorized')
def unauthorized():
    return render_template('unauthorized.html')

'''INVENTORY ROUTE V2'''
@app.route('/inventory')
def inventory():

    if 'user_id' not in session:
        return redirect('/login')
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔵 Categories
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    # 🔵 Category Filter
    selected_category = request.args.get('category', 'all')

    # 🔥 MAIN INVENTORY QUERY
    query = """
        SELECT
        p.id,
        p.name,
        c.name,
        p.quantity,
        
        (
        SELECT pi.selling_price
        FROM purchase_items pi
        WHERE pi.product_id = p.id
        ORDER BY pi.id DESC
        LIMIT 1
        ) AS latest_price,
        
        (
        SELECT COUNT(*)
        FROM purchase_items pi
        WHERE pi.product_id = p.id
        ) AS purchase_count
        
        FROM products p
        LEFT JOIN categories c
        ON p.category_id = c.id
    """

    params = ()

    # 🔵 FILTERING
    if selected_category != "all":
        query += " WHERE p.category_id = %s"
        params = (selected_category,)

    query += " ORDER BY p.id DESC"

    cursor.execute(query, params)

    inventory = cursor.fetchall()

    # 🔵 SUMMARY
    total_quantity = 0

    for item in inventory:
        total_quantity += item[3]

    conn.close()

    return render_template(
        'inventory.html',
        inventory=inventory,
        categories=categories,
        selected_category=selected_category,
        total_quantity=total_quantity
    )




'''ADD CATEGORY'''
@app.route('/add_category', methods=['POST'])
def add_category():
    if 'user_id' not in session:
        return redirect('/login')
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================
    

    name = request.form['cat_name']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO categories (name) VALUES (%s)", (name,))
    conn.commit()
    conn.close()

    return redirect('/inventory')



'''ADD PRODUCT V2'''
@app.route('/add_product', methods=['POST'])
def add_product():

    if 'user_id' not in session:
        return redirect('/login')
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================

    category_id = request.form['category_id']
    name = request.form['name']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products
        (category_id, name, quantity)
        VALUES (%s, %s, 0)
    """, (category_id, name))

    conn.commit()
    conn.close()

    return redirect('/inventory')

'''Edit Product Route'''
@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):

    if 'user_id' not in session:
        return redirect('/login')

    # ================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    # ================================================================

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔒 CHECK WHETHER PRODUCT HAS PURCHASE HISTORY
    cursor.execute("""
        SELECT COUNT(*)
        FROM purchase_items
        WHERE product_id = %s
    """, (id,))

    purchase_count = cursor.fetchone()[0]

    if purchase_count > 0:
        conn.close()
        return redirect('/inventory?error=locked')

    # 🔵 GET CATEGORIES
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    if request.method == 'POST':

        name = request.form['name']
        category_id = request.form['category_id']

        cursor.execute("""
            UPDATE products
            SET name=%s,
                category_id=%s
            WHERE id=%s
        """, (name, category_id, id))

        conn.commit()
        conn.close()

        return redirect('/inventory')

    # 🔵 GET PRODUCT
    cursor.execute("""
        SELECT *
        FROM products
        WHERE id=%s
    """, (id,))

    product = cursor.fetchone()

    conn.close()

    return render_template(
        'edit_product.html',
        product=product,
        categories=categories
    )


'''DELETE PRODUCT'''
@app.route('/delete_product/<int:id>')
def delete_product(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    return redirect('/inventory')





'''ADD STOCK → REDIRECT TO PURCHASE (Newer version)'''
@app.route('/add_stock/<int:id>')
def add_stock(id):
    if 'user_id' not in session:
        return redirect('/login')

    return redirect(f'/purchase?product_id={id}')
    




'''SALES ROUTE V2'''
@app.route('/sales')
def sales():

    if 'user_id' not in session:
        return redirect('/login')
    #-------------------------------------------------------------
    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')
    #------------------------------------------------------------

    category_id = request.args.get('category_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔵 GET CATEGORIES
    cursor.execute("""
        SELECT *
        FROM categories
        ORDER BY name ASC
    """)
    categories = cursor.fetchall()

    # 🔵 PRODUCTS + LATEST SELLING PRICE
    if category_id and category_id != "all":

        cursor.execute("""
            SELECT
                p.id,
                p.name,
                c.name AS category_name,

                p.quantity,

                (
                    SELECT pi.selling_price
                    FROM purchase_items pi
                    WHERE pi.product_id = p.id
                    ORDER BY pi.id DESC
                    LIMIT 1
                ) AS latest_price

            FROM products p

            LEFT JOIN categories c
            ON p.category_id = c.id

            WHERE p.category_id = %s
            AND p.quantity > 0

            ORDER BY p.name ASC
        """, (category_id,))

    else:

        cursor.execute("""
            SELECT
                p.id,
                p.name,
                c.name AS category_name,

                p.quantity,

                (
                    SELECT pi.selling_price
                    FROM purchase_items pi
                    WHERE pi.product_id = p.id
                    ORDER BY pi.id DESC
                    LIMIT 1
                ) AS latest_price

            FROM products p

            LEFT JOIN categories c
            ON p.category_id = c.id

            WHERE p.quantity > 0

            ORDER BY p.name ASC
        """)

    products = cursor.fetchall()

    # 🔵 CUSTOMERS
    cursor.execute("""
        SELECT *
        FROM customers
        ORDER BY name ASC
    """)
    customers = cursor.fetchall()

    conn.close()

    return render_template(
        'sales.html',
        categories=categories,
        products=products,
        customers=customers,
        selected_category=category_id
    )




'''RECEIPT ROUTE'''
@app.route('/receipt/<int:sale_id>')
def receipt(sale_id):
    if 'user_id' not in session:
        return redirect('/login')
    #-------------------------------------------------------------
    if session.get('role') not in ['admin', 'sales']:
        return redirect('/unauthorized')
    #------------------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()

    # Sale info
    cursor.execute("""
        SELECT s.id, s.total_amount, s.is_credit, c.name
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE s.id=%s
    """, (sale_id,))
    sale = cursor.fetchone()

    # Items
    cursor.execute("""
        SELECT p.name, si.quantity, si.unit_price
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        WHERE si.sale_id=%s
    """, (sale_id,))
    items = cursor.fetchall()

    conn.close()

    return render_template('receipt.html', sale=sale, items=items)





'''COMPLETE SALE: BACKEND ROUTE'''
@app.route('/complete_sale', methods=['POST'])
def complete_sale():

    if 'user_id' not in session:
        return {"status": "error", "message": "Unauthorized"}

    data = request.get_json()

    cart = data['cart']
    total_amount = data['total']

    customer_id = data.get('customer_id') or None
    is_credit = data.get('is_credit', False)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # =========================================
        # STEP 1: CHECK STOCK
        # =========================================
        for item in cart:

            product_id = item['id']
            qty_requested = item['qty']

            cursor.execute("""
                SELECT quantity
                FROM products
                WHERE id = %s
            """, (product_id,))

            result = cursor.fetchone()

            if not result:
                return {
                    "status": "error",
                    "message": f"Product ID {product_id} not found."
                }

            stock = result[0]

            if qty_requested > stock:
                return {
                    "status": "error",
                    "message": f"Not enough stock for product ID {product_id}"
                }

        # =========================================
        # STEP 2: CREATE SALE
        # =========================================
        cursor.execute("""
            INSERT INTO sales
            (customer_id, total_amount, is_credit)
            VALUES (%s, %s, %s)
        """, (
            customer_id,
            total_amount,
            is_credit
        ))

        sale_id = cursor.lastrowid

        # =========================================
        # STEP 3: CREATE RECEIVABLE
        # =========================================
        if is_credit:

            if not customer_id:
                return {
                    "status": "error",
                    "message": "Customer must be selected for credit sales."
                }

            
            cursor.execute("""
                           INSERT INTO receivables
                           (
                           customer_id,
                           sale_id,
                           original_amount,
                           amount_due
                           )
                           VALUES (%s, %s, %s, %s)
                           """, (
                               customer_id,
                               sale_id,
                               total_amount,   # Original amount
                               total_amount    # Current amount due
                               ))

        # =========================================
        # STEP 4: INSERT SALE ITEMS
        # =========================================
        for item in cart:

            product_id = item['id']
            qty = int(item['qty'])
            selling_price = float(item['price'])

            # 🔥 GET LATEST PURCHASE COST
            cursor.execute("""
                SELECT buying_price, extra_cost
                FROM purchase_items
                WHERE product_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (product_id,))

            latest_purchase = cursor.fetchone()

            if latest_purchase:
                buying_price = float(latest_purchase[0])
                extra_cost = float(latest_purchase[1])

                cost_price = buying_price + extra_cost

            else:
                # fallback protection
                cost_price = 0

            # 🔵 INSERT SALE ITEM
            cursor.execute("""
                INSERT INTO sale_items
                (
                    sale_id,
                    product_id,
                    quantity,
                    unit_price,
                    cost_price
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                sale_id,
                product_id,
                qty,
                selling_price,
                cost_price
            ))

            # 🔴 REDUCE STOCK
            cursor.execute("""
                UPDATE products
                SET quantity = quantity - %s
                WHERE id = %s
            """, (
                qty,
                product_id
            ))

        conn.commit()

        return {
            "status": "success",
            "sale_id": sale_id
        }

    except Exception as e:

        conn.rollback()

        return {
            "status": "error",
            "message": str(e)
        }

    finally:
        conn.close()







'''SALES HISTORY'''
@app.route('/sales_history')
def sales_history():

    if 'user_id' not in session:
        return redirect('/login')

    # ============================================================
    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')
    # ============================================================

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            si.id,

            c.name,

            p.name,

            si.quantity,

            si.unit_price,

            s.total_amount,

            s.created_at,

            p.quantity,

            s.is_credit,

            COALESCE(
                (
                    SELECT SUM(sr.returned_quantity)
                    FROM sales_returns sr
                    WHERE sr.sale_item_id = si.id
                ),
                0
            ) AS returned_qty,

            (
                si.quantity -
                COALESCE(
                    (
                        SELECT SUM(sr.returned_quantity)
                        FROM sales_returns sr
                        WHERE sr.sale_item_id = si.id
                    ),
                    0
                )
            ) AS available_return

        FROM sale_items si

        LEFT JOIN sales s
            ON si.sale_id = s.id

        LEFT JOIN customers c
            ON s.customer_id = c.id

        LEFT JOIN products p
            ON si.product_id = p.id

        ORDER BY s.created_at DESC

    """)

    sales = cursor.fetchall()

    conn.close()

    return render_template(
        "sales_history.html",
        sales=sales
    )

















'''ADD CUSTOMERS PAGE ROUTE'''
@app.route('/customers')
def customers():
    if 'user_id' not in session:
        return redirect('/login')
    #-------------------------------------------------------------
    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')
    #------------------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM customers")
    customers = cursor.fetchall()

    conn.close()

    return render_template('customers.html', customers=customers)

'''Add Customer button'''
@app.route('/add_customer', methods=['POST'])
def add_customer():
    name = request.form['name']
    phone = request.form['phone']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO customers (name, phone) VALUES (%s, %s)", (name, phone))
    conn.commit()
    conn.close()

    return redirect('/customers')


'''RECEIVABLES PAGE'''
@app.route('/receivables')
def receivables():

    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')

    conn = get_db_connection()
    cursor = conn.cursor()

    # ===============================
    # GET CUSTOMERS FOR FILTER
    # ===============================
    cursor.execute("""
        SELECT id, name
        FROM customers
        ORDER BY name
    """)
    customers = cursor.fetchall()

    # Selected customer
    selected_customer = request.args.get("customer_id", "all")
    hide_paid = request.args.get("hide_paid") == "1"

    # ===============================
    # RECEIVABLES QUERY
    # ===============================
    query = """
        SELECT
            r.id,
            c.id,
            c.name,
            r.amount_due,
            s.created_at

        FROM receivables r

        LEFT JOIN customers c
            ON r.customer_id = c.id

        LEFT JOIN sales s
            ON r.sale_id = s.id

        WHERE 1=1
    """

    params = []

    # Customer filter
    if selected_customer != "all":
        query += " AND r.customer_id = %s"
        params.append(selected_customer)

    # Hide fully paid
    if hide_paid:
        query += " AND r.amount_due > 0"

    query += " ORDER BY s.created_at DESC"

    cursor.execute(query, params)

    receivables = cursor.fetchall()

    conn.close()

    return render_template(
        "receivables.html",
        receivables=receivables,
        customers=customers,
        selected_customer=selected_customer,
        hide_paid=hide_paid
    )









'''CUSTOMER PAYMENT HISTORY'''
@app.route('/payment_history/<int:receivable_id>')
def payment_history(receivable_id):

    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')

    conn = get_db_connection()
    cursor = conn.cursor()

    # ============================================
    # ORIGINAL CREDIT SALE INFORMATION
    # ============================================
    cursor.execute("""
        SELECT
            c.name,
            s.created_at,
            r.original_amount,
            r.amount_due
        FROM receivables r

        LEFT JOIN customers c
            ON r.customer_id = c.id

        LEFT JOIN sales s
            ON r.sale_id = s.id

        WHERE r.id = %s
    """, (receivable_id,))

    sale = cursor.fetchone()

    if not sale:
        conn.close()
        return "Receivable not found."

    # ============================================
    # CUSTOMER PAYMENTS
    # ============================================
    cursor.execute("""
        SELECT
            amount_paid,
            payment_link,
            created_at
        FROM receivable_payments

        WHERE receivable_id = %s

        ORDER BY created_at ASC
    """, (receivable_id,))

    payments = cursor.fetchall()

    # ============================================___
    # SALES RETURNS
    # ============================================___
    cursor.execute("""
        SELECT
            sr.returned_amount,
            sr.reason,
            sr.created_at
        FROM sales_returns sr

        JOIN sale_items si
            ON sr.sale_item_id = si.id

        JOIN receivables r
            ON r.sale_id = si.sale_id

        WHERE r.id = %s

        ORDER BY sr.created_at ASC
    """, (receivable_id,))

    returns = cursor.fetchall()

    # ============================================
    # BUILD LEDGER
    # ============================================

    ledger = []

    balance = float(sale[2])      # original_amount

    # Initial Credit Sale
    ledger.append({
        "date": sale[1],
        "type": "sale",
        "description": "Credit Sale",
        "debit": float(sale[2]),
        "credit": 0,
        "balance": balance
    })

    # Customer Payments
    for payment in payments:

        balance -= float(payment[0])

        ledger.append({
            "date": payment[2],
            "type": "payment",
            "description": payment[1] if payment[1] else "Customer Payment",
            "debit": 0,
            "credit": float(payment[0]),
            "balance": max(balance, 0)
        })

    # Sales Returns
    for returned in returns:

        balance -= float(returned[0])

        ledger.append({
            "date": returned[2],
            "type": "return",
            "description": returned[1] if returned[1] else "Sales Return",
            "debit": 0,
            "credit": float(returned[0]),
            "balance": max(balance, 0)
        })

    # ============================================
    # SORT LEDGER CHRONOLOGICALLY
    # ============================================

    ledger.sort(key=lambda x: x["date"])

    conn.close()

    return render_template(
        "payment_history.html",
        receivable=sale,
        ledger=ledger
    )






























'''PAYMENT RECEIVABLE ROUTE'''
@app.route('/pay_receivable/<int:id>', methods=['POST'])
def pay_receivable(id):
    if 'user_id' not in session:
        return redirect('/login')

    amount = float(request.form['amount'])
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get current balance (Payment Validation)
    cursor.execute("SELECT amount_due FROM receivables WHERE id=%s", (id,))
    current_due = cursor.fetchone()[0]

    if amount > current_due:
        conn.close()
        return "Error: Payment exceeds amount due"

    reference_note = request.form.get('reference_note', '')

    # 1. Reduce receivable
    cursor.execute("""
        UPDATE receivables
        SET amount_due = amount_due - %s
        WHERE id = %s
    """, (amount, id))

    # 2. Record payment history
    cursor.execute("""
        INSERT INTO receivable_payments (receivable_id, amount_paid, payment_link)
                   VALUES (%s, %s, %s)
    """, (id, amount, reference_note))

    conn.commit()
    conn.close()

    return redirect('/receivables')





'''CUSTOMER BALANCE VIEW'''
@app.route('/customer_balance/<int:customer_id>')
def customer_balance(customer_id):
    if 'user_id' not in session:
        return redirect('/login')
    #-------------------------------------------------------------
    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')
    #------------------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()

    # Customer name
    cursor.execute("SELECT name FROM customers WHERE id=%s", (customer_id,))
    customer = cursor.fetchone()

    # Total debt
    cursor.execute("""
        SELECT SUM(amount_due)
        FROM receivables
        WHERE customer_id=%s
    """, (customer_id,))
    total_due = cursor.fetchone()[0] or 0

    conn.close()

    return render_template('customer_balance.html',
                           customer=customer,
                           total_due=total_due)




'''REPORT SYSTEM V2'''
from datetime import datetime, timedelta

@app.route('/reports')
def reports():

    if 'user_id' not in session:
        return redirect('/login')
    # -------------------------------------------
    if session.get('role') != 'admin':
        return redirect('/unauthorized')
    #--------------------------------------------

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_db_connection()
    cursor = conn.cursor()

    today = datetime.today().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # =====================================================
    # SALES SUMMARY
    # =====================================================

    # TODAY SALES
    cursor.execute("""
        SELECT IFNULL(SUM(total_amount), 0)
        FROM sales
        WHERE DATE(created_at) = %s
    """, (today,))
    today_sales = cursor.fetchone()[0]

    # WEEK SALES
    cursor.execute("""
        SELECT IFNULL(SUM(total_amount), 0)
        FROM sales
        WHERE created_at >= %s
    """, (week_ago,))
    weekly_sales = cursor.fetchone()[0]

    # MONTH SALES
    cursor.execute("""
        SELECT IFNULL(SUM(total_amount), 0)
        FROM sales
        WHERE created_at >= %s
    """, (month_ago,))
    monthly_sales = cursor.fetchone()[0]

    # =====================================================
    # FILTER
    # =====================================================

    params = []

    sale_filter = ""
    if start_date and end_date:
        sale_filter = "WHERE DATE(s.created_at) BETWEEN %s AND %s"
        params = [start_date, end_date]

    # =====================================================
    # TOTAL REVENUE
    # =====================================================

    revenue_query = f"""
        SELECT IFNULL(SUM(s.total_amount), 0)
        FROM sales s
        {sale_filter}
    """

    cursor.execute(revenue_query, params)
    total_revenue = cursor.fetchone()[0]

    # =====================================================
    # TOTAL PROFIT
    # =====================================================

    profit_query = f"""
        SELECT IFNULL(
            SUM(
                (si.unit_price - si.cost_price) * si.quantity
            ),
        0)
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        {sale_filter}
    """

    cursor.execute(profit_query, params)
    total_profit = cursor.fetchone()[0]

    # =====================================================
    # TOTAL ITEMS SOLD
    # =====================================================

    items_query = f"""
        SELECT IFNULL(SUM(si.quantity), 0)
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        {sale_filter}
    """

    cursor.execute(items_query, params)
    total_items_sold = cursor.fetchone()[0]

    # =====================================================
    # SALES CHART
    # =====================================================

    if start_date and end_date:

        cursor.execute(f"""
            SELECT DATE(s.created_at), SUM(s.total_amount)
            FROM sales s
            {sale_filter}
            GROUP BY DATE(s.created_at)
            ORDER BY DATE(s.created_at)
        """, params)

    else:

        cursor.execute("""
            SELECT DATE(created_at), SUM(total_amount)
            FROM sales
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
        """)

    chart_data = cursor.fetchall()

    dates = [str(row[0]) for row in chart_data]
    amounts = [float(row[1]) for row in chart_data]

    # =====================================================
    # TOP PRODUCTS
    # =====================================================

    top_query = f"""
        SELECT 
            p.name,
            SUM(si.quantity) AS total_qty
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        JOIN sales s ON si.sale_id = s.id
        {sale_filter}
        GROUP BY p.name
        ORDER BY total_qty DESC
        LIMIT 5
    """

    cursor.execute(top_query, params)
    top_products = cursor.fetchall()

    conn.close()

    return render_template(
        'reports.html',

        today_sales=today_sales,
        weekly_sales=weekly_sales,
        monthly_sales=monthly_sales,

        total_revenue=total_revenue,
        total_profit=total_profit,

        total_items_sold=total_items_sold,

        dates=dates,
        amounts=amounts,

        top_products=top_products,

        start_date=start_date,
        end_date=end_date
    )




'''PAYABLES PAGE'''
'''PAYABLES PAGE'''
@app.route('/payables')
def payables():

    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')

    conn = get_db_connection()
    cursor = conn.cursor()

    # ===============================
    # GET ALL SUPPLIERS FOR FILTER
    # ===============================
    cursor.execute("""
        SELECT id, name
        FROM suppliers
        ORDER BY name
    """)
    suppliers = cursor.fetchall()

    # Selected supplier
    selected_supplier = request.args.get("supplier_id", "all")

    hide_paid = request.args.get("hide_paid")

    # ===============================
    # PAYABLES QUERY
    # ===============================
    query = """
        SELECT
            p.id,
            s.name AS supplier_name,
            pr.name AS product_name,
            pi.quantity,
            (pi.buying_price + pi.extra_cost) AS unit_cost,
            p.amount_due,
            pu.created_at,
            pi.description

        FROM payables p

        LEFT JOIN suppliers s
            ON p.supplier_id = s.id

        LEFT JOIN purchases pu
            ON p.purchase_id = pu.id

        LEFT JOIN purchase_items pi
            ON pu.id = pi.purchase_id

        LEFT JOIN products pr
            ON pi.product_id = pr.id

        WHERE p.purchase_id IS NOT NULL
    """

    params = []

    # Filter by supplier
    if selected_supplier != "all":
        query += " AND p.supplier_id = %s"
        params.append(selected_supplier)
    
    # Hide fully paid payables
    if hide_paid:
        query += " AND p.amount_due > 0"
    
    query += " ORDER BY pu.created_at DESC"
    

    cursor.execute(query, params)
    payables = cursor.fetchall()

    conn.close()

    return render_template(
    "payables.html",
    payables=payables,
    suppliers=suppliers,
    selected_supplier=selected_supplier,
    hide_paid=hide_paid
    )


'''PAYMENT(PAYABLES) ROUTE'''
@app.route('/pay_payable/<int:id>', methods=['POST'])
def pay_payable(id):
    if 'user_id' not in session:
        return redirect('/login')
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================

    try:
        amount = float(request.form['amount'])
    except:
        return redirect('/payables?error=invalid')

    payment_link = request.form.get('payment_link', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 🔴 1. GET CURRENT DUE
        cursor.execute("SELECT amount_due FROM payables WHERE id=%s", (id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return redirect('/payables?error=notfound')

        current_due = float(result[0])

        # 🔴 2. VALIDATIONS (STRONG)
        if current_due <= 0:
            conn.close()
            return redirect('/payables?error=paid')

        if amount <= 0:
            conn.close()
            return redirect('/payables?error=invalid_amount')

        if amount > current_due:
            conn.close()
            return redirect('/payables?error=overpay')

        # 🟢 3. UPDATE PAYABLE
        new_due = current_due - amount

        cursor.execute("""
            UPDATE payables
            SET amount_due = %s
            WHERE id = %s
        """, (new_due, id))

        # 🟢 4. RECORD PAYMENT
        cursor.execute("""
            INSERT INTO payable_payments (payable_id, amount_paid, payment_link)
            VALUES (%s, %s, %s)
        """, (id, amount, payment_link))

        conn.commit()
        conn.close()

        return redirect('/payables?success=1')

    except Exception as e:
        conn.rollback()
        conn.close()
        return redirect('/payables?error=server')
    




'''PAYABLE HISTORY PAGE'''
@app.route('/payable_history/<int:payable_id>')
def payable_history(payable_id):

    if 'user_id' not in session:
        return redirect('/login')

    # ================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    # ================================================================

    conn = get_db_connection()
    cursor = conn.cursor()

    # ================================================================
    # PURCHASE INFORMATION
    # ================================================================

    cursor.execute("""
        SELECT
            s.name,
            pr.name,
            pi.quantity,
            (pi.buying_price + pi.extra_cost) AS unit_cost,
            (pi.buying_price * pi.quantity) AS original_amount,
            pu.created_at,
            pi.description

        FROM payables p

        LEFT JOIN suppliers s
            ON p.supplier_id = s.id

        LEFT JOIN purchases pu
            ON p.purchase_id = pu.id

        LEFT JOIN purchase_items pi
            ON pu.id = pi.purchase_id

        LEFT JOIN products pr
            ON pi.product_id = pr.id

        WHERE p.id=%s
    """, (payable_id,))

    purchase = cursor.fetchone()

    # ================================================================
    # PAYMENT HISTORY
    # ================================================================

    cursor.execute("""
        SELECT
            amount_paid,
            payment_link,
            created_at

        FROM payable_payments

        WHERE payable_id=%s

        ORDER BY created_at ASC
    """, (payable_id,))

    payments = cursor.fetchall()

    # ================================================================
    # RETURN HISTORY
    # ================================================================

    cursor.execute("""
        SELECT
            pr.refund_amount,
            pr.returned_quantity,
            pr.reason,
            pr.created_at

        FROM purchase_returns pr

        JOIN purchase_items pi
            ON pr.purchase_item_id = pi.id

        JOIN purchases pu
            ON pi.purchase_id = pu.id

        JOIN payables pa
            ON pa.purchase_id = pu.id

        WHERE pa.id=%s

        ORDER BY pr.created_at ASC
    """, (payable_id,))

    returns = cursor.fetchall()

    # ================================================================
    # BUILD LEDGER
    # ================================================================

    ledger = []

    ledger.append({
        "date": purchase[5],
        "description": "Initial Purchase",
        "debit": float(purchase[4]),
        "credit": 0,
        "type": "purchase"
    })

    # Product Returns
    for r in returns:

        ledger.append({

            "date": r[3],

            "description":
                f"Returned {r[1]} item(s)"
                if not r[2]
                else r[2],

            "debit": 0,

            "credit": float(r[0]),

            "type": "return"

        })

    # Payments
    for p in payments:

        ledger.append({

            "date": p[2],

            "description":
                p[1] if p[1] else "Payment",

            "debit": 0,

            "credit": float(p[0]),

            "type": "payment"

        })

    # ================================================================
    # SORT BY DATE
    # ================================================================

    ledger.sort(key=lambda x: x["date"])

    # ================================================================
    # RUNNING BALANCE
    # ================================================================

    balance = 0

    for row in ledger:

        balance += row["debit"]
        balance -= row["credit"]

        row["balance"] = balance

    conn.close()

    return render_template(
        "payable_history.html",
        purchase=purchase,
        ledger=ledger
    )



'''SUPPLIERS'''
@app.route('/suppliers')
def suppliers():
    if 'user_id' not in session:
        return redirect('/login')
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers")
    suppliers = cursor.fetchall()
    conn.close()
    return render_template('suppliers.html', suppliers=suppliers)






'''ADD SUPPLIERS'''
@app.route('/add_supplier', methods=['POST'])
def add_supplier():
    name = request.form['name']
    phone = request.form['phone']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO suppliers (name, phone)
        VALUES (%s, %s)
    """, (name, phone))

    conn.commit()
    conn.close()

    return redirect('/suppliers')


'''EXPORT TO EXCEL'''
from openpyxl import Workbook
from flask import send_file
import io

@app.route('/export_excel')
def export_excel():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.id, s.total_amount, s.created_at
        FROM sales s
    """)
    sales = cursor.fetchall()

    conn.close()

    # Create Excel file
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Report"

    ws.append(["Sale ID", "Amount", "Date"])

    for s in sales:
        ws.append(s)

    # Save to memory
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output,
                     download_name="sales_report.xlsx",
                     as_attachment=True)

'''DASHBOARD ROUTE'''
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Today's sales
    cursor.execute("""
        SELECT SUM(total_amount)
        FROM sales
        WHERE DATE(created_at) = CURDATE()
    """)
    today_sales = cursor.fetchone()[0] or 0

    # Low stock
    cursor.execute("""
        SELECT name, quantity
        FROM products
        WHERE quantity < 5
    """)
    low_stock = cursor.fetchall()

    # Receivables
    cursor.execute("SELECT SUM(amount_due) FROM receivables")
    receivables = cursor.fetchone()[0] or 0

    # Payables
    cursor.execute("SELECT SUM(amount_due) FROM payables")
    payables = cursor.fetchone()[0] or 0

    conn.close()

    return render_template('dashboard.html',
                           today_sales=today_sales,
                           low_stock=low_stock,
                           receivables=receivables,
                           payables=payables)




'''PURCHASE PAGE V2'''
@app.route('/purchase/<int:product_id>')
def purchase(product_id):

    if 'user_id' not in session:
        return redirect('/login')
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔵 GET PRODUCT
    cursor.execute("""
        SELECT products.id,
               products.name,
               categories.name
        FROM products
        LEFT JOIN categories
        ON products.category_id = categories.id
        WHERE products.id = %s
    """, (product_id,))

    product = cursor.fetchone()

    # 🔵 GET SUPPLIERS
    cursor.execute("SELECT * FROM suppliers")
    suppliers = cursor.fetchall()

    conn.close()

    return render_template(
        'purchase.html',
        product=product,
        suppliers=suppliers
    )







'''COMPLETE PURCHASE V2'''
@app.route('/complete_purchase', methods=['POST'])
def complete_purchase():

    if 'user_id' not in session:
        return redirect('/login')

    product_id = request.form['product_id']
    supplier_id = request.form['supplier_id']

    buying_price = float(request.form['buying_price'])
    extra_cost = float(request.form['extra_cost'])

    quantity = int(request.form['quantity'])

    selling_price = float(request.form['selling_price'])

    description = request.form['description']

    is_credit = request.form.get('is_credit') == 'on'

    supplier_payable_amount = buying_price * quantity

    # 🔥 TOTAL COST
    unit_cost = buying_price + extra_cost
    total_amount = unit_cost * quantity

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # 🔵 CREATE PURCHASE
        cursor.execute("""
            INSERT INTO purchases
            (supplier_id, total_amount, is_credit)
            VALUES (%s, %s, %s)
        """, (supplier_id, total_amount, is_credit))

        purchase_id = cursor.lastrowid

        # 🔵 CREATE PURCHASE ITEM
        cursor.execute("""
            INSERT INTO purchase_items
            (
                purchase_id,
                product_id,
                quantity,
                buying_price,
                extra_cost,
                selling_price,
                description
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            purchase_id,
            product_id,
            quantity,
            buying_price,
            extra_cost,
            selling_price,
            description
        ))

        # 🔵 UPDATE STOCK
        cursor.execute("""
            UPDATE products
            SET quantity = quantity + %s
            WHERE id = %s
        """, (quantity, product_id))

        # 🔴 CREATE PAYABLE
        if is_credit:

            cursor.execute("""
                INSERT INTO payables
                (supplier_id, purchase_id, amount_due)
                VALUES (%s, %s, %s)
            """, (
                supplier_id,
                purchase_id,
                supplier_payable_amount
            ))

        conn.commit()
        conn.close()

        return redirect('/inventory')

    except Exception as e:

        conn.rollback()
        conn.close()

        return f"ERROR: {str(e)}"


'''Supplier Dashboard'''
@app.route('/supplier_dashboard')
def supplier_dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔵 Get total due per supplier
    cursor.execute("""
        SELECT 
            s.id,
            s.name,
            IFNULL(SUM(p.amount_due), 0) as total_due
        FROM suppliers s
        LEFT JOIN payables p ON s.id = p.supplier_id
        GROUP BY s.id, s.name
        ORDER BY total_due DESC
    """)

    suppliers = cursor.fetchall()

    # 🔵 Get total exposure
    cursor.execute("""
        SELECT IFNULL(SUM(amount_due), 0) FROM payables
    """)
    total_exposure = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'supplier_dashboard.html',
        suppliers=suppliers,
        total_exposure=total_exposure
    )

'''PURCHASE HISTORY'''
@app.route('/purchase_history')
def purchase_history():

    if 'user_id' not in session:
        return redirect('/login')

    # ================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    # ================================================================

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""

        SELECT

            pi.id,

            pu.created_at,

            s.name,

            pr.name,

            pi.quantity,

            pi.buying_price,

            pu.is_credit,

            pr.quantity AS current_stock,

            IFNULL((
                SELECT SUM(returned_quantity)
                FROM purchase_returns
                WHERE purchase_item_id = pi.id
            ),0) AS returned_qty

        FROM purchase_items pi

        JOIN purchases pu
            ON pi.purchase_id = pu.id

        JOIN suppliers s
            ON pu.supplier_id = s.id

        JOIN products pr
            ON pi.product_id = pr.id

        ORDER BY pu.created_at DESC

    """)

    rows = cursor.fetchall()

    purchase_history = []

    for row in rows:

        purchase_item_id = row[0]
        purchase_date = row[1]
        supplier = row[2]
        product = row[3]
        purchased_qty = row[4]
        buying_price = row[5]
        is_credit = row[6]
        current_stock = row[7]
        returned_qty = row[8]

        remaining_purchase = purchased_qty - returned_qty

        available_return = min(
            remaining_purchase,
            current_stock
        )

        purchase_history.append({

            "purchase_item_id": purchase_item_id,
            "date": purchase_date,
            "supplier": supplier,
            "product": product,
            "purchased_qty": purchased_qty,
            "buying_price": buying_price,
            "is_credit": is_credit,
            "current_stock": current_stock,
            "returned_qty": returned_qty,
            "available_return": available_return

        })

    conn.close()

    return render_template(
        "purchase_history.html",
        purchases=purchase_history
    )


'''PURCHASE RETURN'''
@app.route('/purchase_return/<int:purchase_item_id>', methods=['GET', 'POST'])
def purchase_return(purchase_item_id):

    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')

    conn = get_db_connection()
    cursor = conn.cursor()

    # ==========================================================
    # GET PURCHASE INFORMATION
    # ==========================================================

    cursor.execute("""
        SELECT
            pi.id,
            s.name,
            p.name,
            pu.created_at,
            pu.is_credit,
            pi.buying_price,
            pi.extra_cost,
            pi.quantity,

            (
                SELECT IFNULL(SUM(returned_quantity),0)
                FROM purchase_returns
                WHERE purchase_item_id = pi.id
            ) AS returned_qty,

            p.quantity,

            LEAST(
                pi.quantity -
                (
                    SELECT IFNULL(SUM(returned_quantity),0)
                    FROM purchase_returns
                    WHERE purchase_item_id = pi.id
                ),
                p.quantity
            ) AS available_return

        FROM purchase_items pi

        JOIN purchases pu
            ON pi.purchase_id = pu.id

        JOIN suppliers s
            ON pu.supplier_id = s.id

        JOIN products p
            ON pi.product_id = p.id

        WHERE pi.id=%s
    """, (purchase_item_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return "Purchase not found."

    purchase = {
        "purchase_item_id": row[0],
        "supplier": row[1],
        "product": row[2],
        "date": row[3],
        "is_credit": row[4],
        "buying_price": float(row[5]),
        "extra_cost": float(row[6]),
        "purchased_qty": row[7],
        "returned_qty": row[8],
        "current_stock": row[9],
        "available_return": row[10]
    }

    # ==========================================================
    # SHOW PAGE
    # ==========================================================

    if request.method == "GET":

        conn.close()

        return render_template(
            "purchase_return.html",
            purchase=purchase
        )

    # ==========================================================
    # RETURN PRODUCT
    # ==========================================================

    returned_qty = int(request.form["returned_quantity"])

    return_type = request.form["return_type"]

    reason = request.form["reason"]

    if returned_qty <= 0:

        conn.close()

        return "Invalid quantity."

    if returned_qty > purchase["available_return"]:

        conn.close()

        return "Return quantity exceeds available quantity."

    refund_amount = purchase["buying_price"] * returned_qty

    try:

        # Purchase info again
        cursor.execute("""
            SELECT purchase_id, product_id
            FROM purchase_items
            WHERE id=%s
        """, (purchase_item_id,))

        purchase_info = cursor.fetchone()

        purchase_id = purchase_info[0]
        product_id = purchase_info[1]

        # Record return
        cursor.execute("""
            INSERT INTO purchase_returns
            (
                purchase_item_id,
                returned_quantity,
                buying_price,
                extra_cost,
                refund_amount,
                return_type,
                reason
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            purchase_item_id,
            returned_qty,
            purchase["buying_price"],
            0,
            refund_amount,
            return_type,
            reason
        ))

        # Reduce stock
        cursor.execute("""
            UPDATE products
            SET quantity = quantity - %s
            WHERE id=%s
        """, (
            returned_qty,
            product_id
        ))

        # Reduce payable if credit
        if purchase["is_credit"]:

            cursor.execute("""
                UPDATE payables
                SET amount_due = amount_due - %s
                WHERE purchase_id=%s
            """, (
                refund_amount,
                purchase_id
            ))

        conn.commit()

    except Exception as e:

        conn.rollback()

        return str(e)

    finally:

        conn.close()

    return redirect("/purchase_history")







'''SALES RETURN'''
@app.route('/sales_return/<int:sale_item_id>', methods=['GET', 'POST'])
def sales_return(sale_item_id):

    if 'user_id' not in session:
        return redirect('/login')

    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')

    conn = get_db_connection()
    cursor = conn.cursor()

    # ==========================================================
    # GET SALE INFORMATION
    # ==========================================================

    cursor.execute("""
        SELECT

            si.id,
            si.sale_id,
            si.product_id,

            c.name,

            p.name,

            s.created_at,

            s.is_credit,

            s.customer_id,

            si.unit_price,

            si.quantity,

            p.quantity,

            COALESCE(
                (
                    SELECT SUM(returned_quantity)
                    FROM sales_returns
                    WHERE sale_item_id = si.id
                ),
                0
            ) AS returned_qty,

            LEAST(
                si.quantity -
                COALESCE(
                    (
                        SELECT SUM(returned_quantity)
                        FROM sales_returns
                        WHERE sale_item_id = si.id
                    ),
                    0
                ),
                si.quantity
            ) AS available_return

        FROM sale_items si

        JOIN sales s
            ON si.sale_id = s.id

        LEFT JOIN customers c
            ON s.customer_id = c.id

        JOIN products p
            ON si.product_id = p.id

        WHERE si.id = %s

    """, (sale_item_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return "Sale not found."

    sale = {

        "sale_item_id": row[0],
        "sale_id": row[1],
        "product_id": row[2],

        "customer": row[3] if row[3] else "Walk-in Customer",

        "product": row[4],

        "date": row[5],

        "is_credit": row[6],

        "customer_id": row[7],

        "selling_price": float(row[8]),

        "sold_qty": row[9],

        "current_stock": row[10],

        "returned_qty": row[11],

        "available_return": row[12]

    }

    # ==========================================================
    # SHOW PAGE
    # ==========================================================

    if request.method == "GET":

        conn.close()

        return render_template(
            "sales_return.html",
            sale=sale
        )

    # ==========================================================
    # PROCESS RETURN
    # ==========================================================

    returned_qty = int(request.form["returned_quantity"])

    return_type = request.form["return_type"]

    reason = request.form["reason"]

    if returned_qty <= 0:

        conn.close()

        return "Invalid quantity."

    if returned_qty > sale["available_return"]:

        conn.close()

        return "Return quantity exceeds available quantity."

    refund_amount = sale["selling_price"] * returned_qty

    try:

        # ======================================
        # RECORD SALES RETURN
        # ======================================

        
        cursor.execute("""
                       INSERT INTO sales_returns
                       (
                       sale_item_id,
                       returned_quantity,
                       returned_amount,
                       return_type,
                       reason
                       )
                       VALUES (%s,%s,%s,%s,%s)
                       """, (
                           sale_item_id,
                           returned_qty,
                           refund_amount,
                           return_type,
                           reason
                           ))

        # ======================================
        # RETURN PRODUCT TO STOCK
        # ======================================

        cursor.execute("""
            UPDATE products
            SET quantity = quantity + %s
            WHERE id = %s
        """, (

            returned_qty,
            sale["product_id"]

        ))

        # ======================================
        # REDUCE CUSTOMER RECEIVABLE
        # (Credit Sales Only)
        # ======================================

        if sale["is_credit"]:

            cursor.execute("""
                UPDATE receivables
                SET amount_due = amount_due - %s
                WHERE sale_id = %s
            """, (

                refund_amount,
                sale["sale_id"]

            ))

        conn.commit()

    except Exception as e:

        conn.rollback()

        return str(e)

    finally:

        conn.close()

    return redirect("/sales_history")










if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
