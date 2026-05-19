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
            ) AS latest_price

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
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================

    conn = get_db_connection()
    cursor = conn.cursor()

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
                (customer_id, sale_id, amount_due)
                VALUES (%s, %s, %s)
            """, (
                customer_id,
                sale_id,
                total_amount
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
    #-------------------------------------------------------------
    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')
    #------------------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.id, c.id, c.name, r.amount_due, s.created_at
        FROM receivables r
        LEFT JOIN customers c ON r.customer_id = c.id
        LEFT JOIN sales s ON r.sale_id = s.id
        WHERE r.amount_due > 0
    """)

    receivables = cursor.fetchall()

    conn.close()

    return render_template('receivables.html', receivables=receivables)


'''PAYMENT RECEIVABLE ROUTE'''
@app.route('/pay_receivable/<int:id>', methods=['POST'])
def pay_receivable(id):
    if 'user_id' not in session:
        return redirect('/login')
    #-------------------------------------------------------------
    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')
    #------------------------------------------------------------

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

'''PAYMENT HISTORY'''
@app.route('/payment_history/<int:receivable_id>')
def payment_history(receivable_id):
    if 'user_id' not in session:
        return redirect('/login')
    #-------------------------------------------------------------
    if session.get('role') not in ['admin', 'Sales']:
        return redirect('/unauthorized')
    #------------------------------------------------------------

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT amount_paid, payment_link, created_at
        FROM receivable_payments
        WHERE receivable_id=%s
    """, (receivable_id,))

    payments = cursor.fetchall()

    conn.close()

    return render_template('payment_history.html', payments=payments)







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
@app.route('/payables')
def payables():

    if 'user_id' not in session:
        return redirect('/login')
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
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

        ORDER BY pu.created_at DESC
    """)

    payables = cursor.fetchall()

    conn.close()

    return render_template(
        'payables.html',
        payables=payables
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
    




'''payable_history page'''
@app.route('/payable_history/<int:id>')
def payable_history(id):

    if 'user_id' not in session:
        return redirect('/login')
    #================================================================
    if session.get('role') not in ['admin', 'purchaser']:
        return redirect('/unauthorized')
    #================================================================

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔵 PURCHASE INFO
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
        WHERE p.id = %s
    """, (id,))

    purchase = cursor.fetchone()

    # 🔴 PAYMENT HISTORY
    cursor.execute("""
        SELECT 
            amount_paid,
            payment_link,
            created_at
        FROM payable_payments
        WHERE payable_id = %s
        ORDER BY created_at ASC
    """, (id,))

    payments = cursor.fetchall()

    conn.close()

    return render_template(
        'payable_history.html',
        purchase=purchase,
        payments=payments
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



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
