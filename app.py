from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime

app = Flask(__name__, static_folder='public')
app.secret_key = os.environ.get("SECRET_KEY", "devsecretkey")

# ----------------- DATABASE -----------------
def init_db():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    # USERS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0
        )
    ''')

    # ORDERS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT,
            total INTEGER,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

init_db()

# ----------------- HELPERS -----------------
def get_db():
    conn = sqlite3.connect('orders.db')
    conn.row_factory = sqlite3.Row
    return conn

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('is_admin') != 1:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

# ----------------- MAKE ADMIN (keep your original) -----------------
@app.route('/make_admin')
def make_admin():
    conn = get_db()
    conn.execute("UPDATE users SET is_admin=1 WHERE email='hemasaithota3@gmail.com'")
    conn.commit()
    conn.close()
    return "You are now admin"

# ----------------- HOME -----------------
@app.route('/')
@login_required
def home():
    return render_template('product.html', user=session.get('user_name'))

# ----------------- CART -----------------
@app.route('/cart')
@login_required
def cart():
    return render_template('cart.html')

# ----------------- REGISTER -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )
            conn.commit()
        except:
            conn.close()
            return render_template("register.html", error="Email already exists")
        conn.close()
        return redirect('/login')

    return render_template('register.html')

# ----------------- LOGIN -----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            if user['is_banned']:
                return render_template("login.html", error="Your account has been banned. Contact support.")
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['is_admin'] = user['is_admin']
            return redirect('/')
        else:
            return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")

# ----------------- LOGOUT -----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ----------------- PLACE ORDER -----------------
@app.route('/place_order', methods=['POST'])
@login_required
def place_order():
    total = request.form.get('total')
    items = request.form.get('items')
    user_id = session['user_id']

    payment_status = "Success"  # Simulated

    if payment_status == "Success":
        conn = get_db()
        conn.execute(
            "INSERT INTO orders (user_id, items, total) VALUES (?, ?, ?)",
            (user_id, items, total)
        )
        conn.commit()
        conn.close()
        print(f"📧 Email sent to {session['user_name']} - Order Confirmed!")
        return render_template("order_success.html")

    return "Payment Failed"

# ----------------- USER ORDER HISTORY -----------------
@app.route('/my_orders')
@login_required
def my_orders():
    conn = get_db()
    orders = conn.execute(
        "SELECT id, items, total, status, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('my_orders.html', orders=orders)

# ----------------- ADMIN DASHBOARD -----------------
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()

    # Orders with search/filter support
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = '''
        SELECT orders.id, users.name, users.email, orders.items,
               orders.total, orders.status, orders.created_at
        FROM orders
        JOIN users ON orders.user_id = users.id
        WHERE 1=1
    '''
    params = []

    if search:
        query += " AND (users.name LIKE ? OR users.email LIKE ? OR orders.items LIKE ?)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']

    if status_filter:
        query += " AND orders.status = ?"
        params.append(status_filter)

    query += " ORDER BY orders.created_at DESC"
    orders = conn.execute(query, params).fetchall()

    # Analytics
    analytics = conn.execute('''
        SELECT
            COUNT(*) as total_orders,
            COALESCE(SUM(total), 0) as total_revenue,
            COUNT(CASE WHEN status='Pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status='Delivered' THEN 1 END) as delivered,
            COUNT(CASE WHEN status='Cancelled' THEN 1 END) as cancelled
        FROM orders
    ''').fetchone()

    # Revenue by day (last 7 days)
    daily_revenue = conn.execute('''
        SELECT DATE(created_at) as day, SUM(total) as revenue, COUNT(*) as count
        FROM orders
        WHERE created_at >= DATE('now', '-7 days')
        GROUP BY DATE(created_at)
        ORDER BY day
    ''').fetchall()

    conn.close()

    return render_template(
        'admin.html',
        orders=orders,
        analytics=analytics,
        daily_revenue=daily_revenue,
        search=search,
        status_filter=status_filter
    )

# ----------------- UPDATE ORDER STATUS (ADMIN) -----------------
@app.route('/update_status/<int:order_id>', methods=['POST'])
@admin_required
def update_status(order_id):
    new_status = request.form.get('status')
    conn = get_db()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
    conn.commit()
    conn.close()
    return redirect('/admin')

# ----------------- DELETE ORDER (ADMIN) -----------------
@app.route('/delete_order/<int:order_id>', methods=['POST'])
@admin_required
def delete_order(order_id):
    conn = get_db()
    conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

# ----------------- ADMIN USERS -----------------
@app.route('/admin_users')
@admin_required
def admin_users():
    search = request.args.get('search', '').strip()
    conn = get_db()

    if search:
        users = conn.execute(
            "SELECT id, name, email, is_admin, is_banned FROM users WHERE name LIKE ? OR email LIKE ?",
            (f'%{search}%', f'%{search}%')
        ).fetchall()
    else:
        users = conn.execute(
            "SELECT id, name, email, is_admin, is_banned FROM users"
        ).fetchall()

    # Per-user order count & spend
    user_stats = {}
    for u in users:
        stats = conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total),0) as spent FROM orders WHERE user_id=?",
            (u['id'],)
        ).fetchone()
        user_stats[u['id']] = stats

    conn.close()
    return render_template("admin_users.html", users=users, user_stats=user_stats, search=search)

# ----------------- DELETE USER (ADMIN) -----------------
@app.route('/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    conn = get_db()
    # Delete user's orders first (foreign key)
    conn.execute("DELETE FROM orders WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect('/admin_users')

# ----------------- BAN / UNBAN USER (ADMIN) -----------------
@app.route('/ban_user/<int:user_id>', methods=['POST'])
@admin_required
def ban_user(user_id):
    action = request.form.get('action')  # 'ban' or 'unban'
    is_banned = 1 if action == 'ban' else 0
    conn = get_db()
    conn.execute("UPDATE users SET is_banned=? WHERE id=?", (is_banned, user_id))
    conn.commit()
    conn.close()
    return redirect('/admin_users')

# ----------------- TOGGLE ADMIN ROLE -----------------
@app.route('/toggle_admin/<int:user_id>', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    # Prevent removing own admin
    if user_id == session['user_id']:
        return redirect('/admin_users')
    conn = get_db()
    user = conn.execute("SELECT is_admin FROM users WHERE id=?", (user_id,)).fetchone()
    new_val = 0 if user['is_admin'] else 1
    conn.execute("UPDATE users SET is_admin=? WHERE id=?", (new_val, user_id))
    conn.commit()
    conn.close()
    return redirect('/admin_users')

# ----------------- ANALYTICS API (JSON for charts) -----------------
@app.route('/admin/analytics')
@admin_required
def analytics_api():
    conn = get_db()

    daily = conn.execute('''
        SELECT DATE(created_at) as day, SUM(total) as revenue, COUNT(*) as orders
        FROM orders
        WHERE created_at >= DATE('now', '-30 days')
        GROUP BY DATE(created_at)
        ORDER BY day
    ''').fetchall()

    status_counts = conn.execute('''
        SELECT status, COUNT(*) as count FROM orders GROUP BY status
    ''').fetchall()

    conn.close()

    return jsonify({
        'daily': [dict(r) for r in daily],
        'status_counts': [dict(r) for r in status_counts]
    })

# ----------------- USER ORDER DETAIL (ADMIN) -----------------
@app.route('/admin/order/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    conn = get_db()
    order = conn.execute('''
        SELECT orders.*, users.name, users.email
        FROM orders JOIN users ON orders.user_id = users.id
        WHERE orders.id=?
    ''', (order_id,)).fetchone()
    conn.close()
    if not order:
        return "Order not found", 404
    return render_template('admin_order_detail.html', order=order)

# ----------------- PASSWORD RESET -----------------
@app.route('/password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if user:
            session['reset_user'] = email
            return redirect(url_for('reset_password'))
        else:
            return render_template('password.html', error="User not found")

    return render_template('password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        new_password = generate_password_hash(request.form.get('new_password'))
        conn = get_db()
        conn.execute(
            "UPDATE users SET password=? WHERE email=?",
            (new_password, session['reset_user'])
        )
        conn.commit()
        conn.close()
        session.pop('reset_user', None)
        return redirect('/login')

    return render_template('reset_password.html')

# ----------------- RUN -----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
