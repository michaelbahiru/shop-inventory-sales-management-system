from flask import Flask, render_template, request, redirect, session, url_for
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json


app = Flask(__name__)
app.secret_key = "your_secret_key"  # change this later

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect('/portal')
    return redirect('/login')


'''REGISTER ROUTE'''
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']   # ✅ NEW

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
            """, (username, hashed_password, role))
            
            conn.commit()

        except:
            conn.close()
            return "Username already exists!"

        conn.close()
        return redirect('/login')

    return render_template('register.html')

'''LOGIN ROUTE'''
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['role'] = user[3]   # ✅ NEW (store role)

            return redirect('/portal')

        return "Invalid username or password"

    return render_template('login.html')


'''STEP 4 — LOGOUT'''
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

'''STEP 5 — PORTAL PAGE'''
@app.route('/portal')
def portal():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('portal.html')


'''INVENTORY ROUTE (Backend) - FIXED CATEGORY FILTER'''
@app.route('/inventory')
def inventory():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Categories
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    # 2. Suppliers
    cursor.execute("SELECT * FROM suppliers")
    suppliers = cursor.fetchall()

    # 3. Get filter
    category_filter = request.args.get('category')

    # 4. Build query (FIXED LOGIC)
    base_query = """
        SELECT 
            products.id, products.name, categories.name,
            products.selling_price, products.quantity,
            products.buying_price, products.extra_cost
        FROM products
        LEFT JOIN categories ON products.category_id = categories.id
    """

    params = []

    if category_filter and category_filter != "all":
        base_query += " WHERE products.category_id = %s"
        params.append(category_filter)

    cursor.execute(base_query, params)
    inventory = cursor.fetchall()

    # 5. Calculations
    total_stock_value = 0
    total_expected_profit = 0
    total_quantity = 0

    for item in inventory:
        selling_price = float(item[3])
        quantity = int(item[4])
        buying_price = float(item[5] or 0)
        extra_cost = float(item[6] or 0)

        total_cost_per_unit = buying_price + extra_cost
        total_stock_value += total_cost_per_unit * quantity
        total_expected_profit += (selling_price - total_cost_per_unit) * quantity
        total_quantity += quantity

    conn.close()

    return render_template(
        'inventory.html',
        categories=categories,
        suppliers=suppliers,
        inventory=inventory,
        total_stock_value=total_stock_value,
        total_expected_profit=total_expected_profit,
        total_quantity=total_quantity,
        selected_category=category_filter  # 🔥 IMPORTANT
    )


'''ADD CATEGORY'''
@app.route('/add_category', methods=['POST'])
def add_category():
    if 'user_id' not in session:
        return redirect('/login')

    name = request.form['cat_name']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO categories (name) VALUES (%s)", (name,))
    conn.commit()
    conn.close()

    return redirect('/inventory')


'''ADD PRODUCT (CLEAN - NO BUYING LOGIC)'''
@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user_id' not in session:
        return redirect('/login')

    category_id = request.form['category_id']
    supplier_id = request.form['supplier_id']
    name = request.form['name']

    buying_price = float(request.form['buying_price'])
    extra_cost = float(request.form['extra_cost'])
    selling_price = float(request.form['selling_price'])

    # 🔥 IMPORTANT: NO quantity here
    quantity = 0

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO products
        (name, category_id, supplier_id, buying_price, extra_cost, selling_price, quantity)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (name, category_id, supplier_id, buying_price, extra_cost, selling_price, quantity))

    conn.commit()
    conn.close()

    return redirect('/inventory')


'''ADD PRODUCT Older version
@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user_id' not in session:
        return redirect('/login')

    category_id = request.form['category_id']
    supplier_id = request.form['supplier_id']
    is_credit = request.form.get('is_credit') == 'on'

    name = request.form['name']
    buying_price = float(request.form['buying_price'])   # ✅ FIX
    extra_cost = float(request.form['extra_cost'])       # ✅ FIX
    selling_price = float(request.form['selling_price']) # ✅ FIX
    quantity = int(request.form['quantity'])             # ✅ FIX

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🟢 Insert product
    cursor.execute("""
        INSERT INTO products 
        (name, category_id, supplier_id, buying_price, extra_cost, selling_price, quantity)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (name, category_id, supplier_id, buying_price, extra_cost, selling_price, quantity))

    # 🔥 FIXED INDENTATION + LOGIC
    if is_credit:
        total_cost = buying_price * quantity

        cursor.execute("""
            INSERT INTO payables (supplier_id, amount_due)
            VALUES (%s, %s)
        """, (supplier_id, total_cost))

    conn.commit()
    conn.close()

    return redirect('/inventory')
'''

'''EDIT PRODUCT'''
@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['selling_price']
        quantity = request.form['quantity']

        cursor.execute("""
            UPDATE products
            SET name=%s, selling_price=%s, quantity=%s
            WHERE id=%s
        """, (name, price, quantity, id))

        conn.commit()
        conn.close()
        return redirect('/inventory')

    cursor.execute("SELECT * FROM products WHERE id=%s", (id,))
    product = cursor.fetchone()

    conn.close()

    return render_template('edit_product.html', product=product)

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


'''Add Stock Older version
@app.route('/add_stock/<int:id>', methods=['GET', 'POST'])
def add_stock(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        quantity = int(request.form['quantity'])

        cursor.execute("""
            UPDATE products
            SET quantity = quantity + %s
            WHERE id = %s
        """, (quantity, id))

        conn.commit()
        conn.close()

        return redirect('/inventory')

    cursor.execute("SELECT name FROM products WHERE id=%s", (id,))
    product = cursor.fetchone()

    conn.close()

    return render_template('add_stock.html', product=product)
'''

'''ADD STOCK → REDIRECT TO PURCHASE (Newer version)'''
@app.route('/add_stock/<int:id>')
def add_stock(id):
    if 'user_id' not in session:
        return redirect('/login')

    return redirect(f'/purchase?product_id={id}')
    


'''SALES ROUTE - FIXED'''
@app.route('/sales')
def sales():
    if 'user_id' not in session:
        return redirect('/login')

    category_id = request.args.get('category_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔵 Get categories
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()

    # 🔥 FIXED QUERY (WITH STOCK FILTER + CLEAN LOGIC)
    base_query = "SELECT * FROM products WHERE quantity > 0"
    params = []

    if category_id and category_id != "all":
        base_query += " AND category_id = %s"
        params.append(category_id)

    cursor.execute(base_query, params)
    products = cursor.fetchall()

    # 🔵 Customers
    cursor.execute("SELECT * FROM customers")
    customers = cursor.fetchall()

    conn.close()

    return render_template('sales.html',
                           categories=categories,
                           products=products,
                           customers=customers,
                           selected_category=category_id)  # 🔥 important

'''RECEIPT ROUTE'''
@app.route('/receipt/<int:sale_id>')
def receipt(sale_id):
    if 'user_id' not in session:
        return redirect('/login')

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

    # Customer & credit
    customer_id = data.get('customer_id') or None
    is_credit = data.get('is_credit', False)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # STEP 1: CHECK STOCK
        for item in cart:
            product_id = item['id']
            qty_requested = item['qty']

            cursor.execute("SELECT quantity FROM products WHERE id=%s", (product_id,))
            stock = cursor.fetchone()[0]

            if qty_requested > stock:
                return {
                    "status": "error",
                    "message": f"Not enough stock for product ID {product_id}"
                }

        # STEP 2: INSERT SALE
        cursor.execute("""
            INSERT INTO sales (customer_id, total_amount, is_credit)
            VALUES (%s, %s, %s)
        """, (customer_id, total_amount, is_credit))

        sale_id = cursor.lastrowid

        # STEP 3: RECEIVABLE (if credit)
        if is_credit:
            if not customer_id:
                return {
                    "status": "error",
                    "message": "Customer must be selected for credit sales."
                }

            cursor.execute("""
                INSERT INTO receivables (customer_id, sale_id, amount_due)
                VALUES (%s, %s, %s)
            """, (customer_id, sale_id, total_amount))

        # STEP 4: INSERT ITEMS + UPDATE STOCK
        for item in cart:
            product_id = item['id']
            qty = item['qty']
            price = item['price']

            cursor.execute("""
                INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
            """, (sale_id, product_id, qty, price))

            cursor.execute("""
                UPDATE products
                SET quantity = quantity - %s
                WHERE id = %s
            """, (qty, product_id))

        conn.commit()

        # ✅ IMPORTANT CHANGE
        return {"status": "success", "sale_id": sale_id}

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}

    finally:
        conn.close()

'''ADD CUSTOMERS PAGE ROUTE'''
@app.route('/customers')
def customers():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM customers")
    customers = cursor.fetchall()

    conn.close()

    return render_template('customers.html', customers=customers)

'''Add Customer'''
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

'''REPORT ROUTE'''
from datetime import datetime, timedelta

@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect('/login')

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_db_connection()
    cursor = conn.cursor()

    today = datetime.today().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # 🔵 TODAY
    cursor.execute("""
        SELECT SUM(total_amount)
        FROM sales
        WHERE DATE(created_at) = %s
    """, (today,))
    today_sales = cursor.fetchone()[0] or 0

    # 🔵 WEEK
    cursor.execute("""
        SELECT SUM(total_amount)
        FROM sales
        WHERE created_at >= %s
    """, (week_ago,))
    weekly_sales = cursor.fetchone()[0] or 0

    # 🔵 MONTH
    cursor.execute("""
        SELECT SUM(total_amount)
        FROM sales
        WHERE created_at >= %s
    """, (month_ago,))
    monthly_sales = cursor.fetchone()[0] or 0

    # 🔥 FILTER CONDITION
    filter_sql = ""
    params = []

    if start_date and end_date:
        filter_sql = "WHERE DATE(created_at) BETWEEN %s AND %s"
        params = [start_date, end_date]

    # 🔵 REVENUE
    query = "SELECT SUM(total_amount) FROM sales " + filter_sql
    cursor.execute(query, params)
    total_revenue = cursor.fetchone()[0] or 0

    # 🔵 PROFIT (FIXED JOIN WITH SALES)
    profit_query = """
        SELECT SUM((si.unit_price - (p.buying_price + p.extra_cost)) * si.quantity)
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        JOIN sales s ON si.sale_id = s.id
    """

    if start_date and end_date:
        profit_query += " WHERE DATE(s.created_at) BETWEEN %s AND %s"

    cursor.execute(profit_query, params)
    total_profit = cursor.fetchone()[0] or 0

    # 🔵 CHART
    chart_query = """
        SELECT DATE(created_at), SUM(total_amount)
        FROM sales
    """

    if start_date and end_date:
        chart_query += " WHERE DATE(created_at) BETWEEN %s AND %s"
        cursor.execute(chart_query + " GROUP BY DATE(created_at)", params)
    else:
        cursor.execute("""
            SELECT DATE(created_at), SUM(total_amount)
            FROM sales
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
        """)

    daily_sales_data = cursor.fetchall()

    dates = [str(row[0]) for row in daily_sales_data]
    amounts = [float(row[1]) for row in daily_sales_data]

    # 🔵 TOP PRODUCTS (FIXED JOIN)
    top_query = """
        SELECT p.name, SUM(si.quantity)
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        JOIN sales s ON si.sale_id = s.id
    """

    if start_date and end_date:
        top_query += " WHERE DATE(s.created_at) BETWEEN %s AND %s"

    top_query += " GROUP BY p.name ORDER BY SUM(si.quantity) DESC LIMIT 5"

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
        dates=dates,
        amounts=amounts,
        top_products=top_products,
        start_date=start_date,
        end_date=end_date
    )


'''PAYABLES PAGE
@app.route('/payables')
def payables():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, s.name, p.amount_due
        FROM payables p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.amount_due > 0
    """)
    payables = cursor.fetchall()

    conn.close()

    return render_template('payables.html', payables=payables)'''

@app.route('/payables')
def payables():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            p.id,
            s.name AS supplier_name,
            pr.name AS product_name,
            pi.quantity,
            pi.unit_cost,
            p.amount_due,
            pu.created_at

        FROM payables p

        LEFT JOIN suppliers s ON p.supplier_id = s.id
        LEFT JOIN purchases pu ON p.purchase_id = pu.id
        LEFT JOIN purchase_items pi ON pu.id = pi.purchase_id
        LEFT JOIN products pr ON pi.product_id = pr.id

        WHERE p.amount_due > 0
        AND p.purchase_id IS NOT NULL

        ORDER BY pu.created_at DESC
    """)

    payables = cursor.fetchall()
    conn.close()

    return render_template('payables.html', payables=payables)



'''PAYMENT(PAYABLES) ROUTE'''
@app.route('/pay_payable/<int:id>', methods=['POST'])
def pay_payable(id):
    if 'user_id' not in session:
        return redirect('/login')

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
    
    
'''PAYABLE PAYMENT HISTORY
@app.route('/payable_history/<int:id>')
def payable_history(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT amount_paid, payment_link, created_at
        FROM payable_payments
        WHERE payable_id=%s
    """, (id,))

    payments = cursor.fetchall()

    conn.close()

    return render_template('payable_history.html', payments=payments)
    '''
@app.route('/payable_history/<int:id>')
def payable_history(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔵 1. GET PURCHASE INFO
    cursor.execute("""
        SELECT 
            s.name,
            pr.name,
            pi.quantity,
            pi.unit_cost,
            p.amount_due + IFNULL(SUM(pp.amount_paid), 0) AS original_amount,
            pu.created_at
        FROM payables p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        LEFT JOIN purchases pu ON p.purchase_id = pu.id
        LEFT JOIN purchase_items pi ON pu.id = pi.purchase_id
        LEFT JOIN products pr ON pi.product_id = pr.id
        LEFT JOIN payable_payments pp ON p.id = pp.payable_id
        WHERE p.id = %s
        GROUP BY p.id, pr.name, pi.quantity, pi.unit_cost, pu.created_at, s.name
    """, (id,))

    purchase = cursor.fetchone()

    # 🔵 2. GET PAYMENTS
    cursor.execute("""
        SELECT amount_paid, payment_link, created_at
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



'''PURCHASE ROUTE'''
# 🔵 PURCHASE PAGE
@app.route('/purchase')
def purchase():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get products (only active ones ideally)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    # Get suppliers
    cursor.execute("SELECT * FROM suppliers")
    suppliers = cursor.fetchall()

    conn.close()

    return render_template('purchase.html',
                           products=products,
                           suppliers=suppliers)

'''COMPLETE PURCHASE Older version
# 🔴 COMPLETE PURCHASE
@app.route('/complete_purchase', methods=['POST'])
def complete_purchase():
    if 'user_id' not in session:
        return {"status": "error", "message": "Unauthorized"}

    data = request.get_json()

    cart = data.get('cart')
    supplier_id = data.get('supplier_id')
    is_credit = data.get('is_credit')

    if not cart or not supplier_id:
        return {"status": "error", "message": "Missing data"}

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        total_amount = 0

        # 🔥 Calculate total first
        for item in cart.values():
            total_amount += item['qty'] * item['cost']

        # 🔵 1. INSERT INTO purchases
        cursor.execute("""
            INSERT INTO purchases (supplier_id, total_amount, is_credit)
            VALUES (%s, %s, %s)
        """, (supplier_id, total_amount, is_credit))

        purchase_id = cursor.lastrowid

        # 🔵 2. LOOP purchase_items + UPDATE STOCK
        for product_id, item in cart.items():

            qty = int(item['qty'])
            cost = float(item['cost'])

            # Insert purchase item
            cursor.execute("""
                INSERT INTO purchase_items (purchase_id, product_id, quantity, unit_cost)
                VALUES (%s, %s, %s, %s)
            """, (purchase_id, product_id, qty, cost))

            # Update stock
            cursor.execute("""
                UPDATE products
                SET quantity = quantity + %s
                WHERE id = %s
            """, (qty, product_id))

        # 🔴 3. CREATE PAYABLE (ONLY IF CREDIT)
        if is_credit:
            cursor.execute("""
                INSERT INTO payables (supplier_id, amount_due)
                VALUES (%s, %s)
            """, (supplier_id, total_amount))

        conn.commit()
        conn.close()

        return {"status": "success"}

    except Exception as e:
        conn.rollback()
        conn.close()
        return {"status": "error", "message": str(e)}
'''



'''COMPLETE PURCHASE (FINAL CLEAN VERSION)'''
@app.route('/complete_purchase', methods=['POST'])
def complete_purchase():
    if 'user_id' not in session:
        return {"status": "error", "message": "Unauthorized"}

    data = request.get_json()

    cart = data.get('cart')
    supplier_id = data.get('supplier_id')
    is_credit = data.get('is_credit')

    if not cart or not supplier_id:
        return {"status": "error", "message": "Missing data"}

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        total_amount = 0

        # 🔥 1. CALCULATE TOTAL
        for item in cart.values():
            qty = int(item['qty'])
            cost = float(item['cost'])
            total_amount += qty * cost

        # 🔵 2. CREATE PURCHASE
        cursor.execute("""
            INSERT INTO purchases (supplier_id, total_amount, is_credit)
            VALUES (%s, %s, %s)
        """, (supplier_id, total_amount, is_credit))

        purchase_id = cursor.lastrowid  # 🔥 VERY IMPORTANT

        # 🔵 3. INSERT ITEMS + UPDATE STOCK
        for product_id, item in cart.items():

            qty = int(item['qty'])
            cost = float(item['cost'])

            # Insert purchase item
            cursor.execute("""
                INSERT INTO purchase_items (purchase_id, product_id, quantity, unit_cost)
                VALUES (%s, %s, %s, %s)
            """, (purchase_id, product_id, qty, cost))

            # Update stock
            cursor.execute("""
                UPDATE products
                SET quantity = quantity + %s
                WHERE id = %s
            """, (qty, product_id))

        # 🔴 4. CREATE PAYABLE (FIXED VERSION)
        if is_credit:
            cursor.execute("""
                INSERT INTO payables (supplier_id, purchase_id, amount_due)
                VALUES (%s, %s, %s)
            """, (supplier_id, purchase_id, total_amount))

        conn.commit()
        conn.close()

        return {"status": "success"}

    except Exception as e:
        conn.rollback()
        conn.close()
        return {"status": "error", "message": str(e)}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
