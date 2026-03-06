from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "secret123"


# ---------------- DATABASE ----------------
def init_db():

    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """)

    # ORDERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        items TEXT,
        total INTEGER,
        status TEXT DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # CREATE ADMIN IF NOT EXISTS
    cursor.execute("SELECT * FROM users WHERE email=?", ("admin@example.com",))
    admin = cursor.fetchone()

    if admin is None:

        password = generate_password_hash("admin123")

        cursor.execute(
            "INSERT INTO users (name,email,password,is_admin) VALUES (?,?,?,?)",
            ("Admin", "admin@example.com", password, 1)
        )

        print("Admin account created")

    conn.commit()
    conn.close()


init_db()


# ---------------- HOME ----------------
@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "product.html",
        user=session["user_name"],
        is_admin=session["is_admin"]
    )


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect("orders.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users(name,email,password) VALUES(?,?,?)",
                (name, email, password)
            )
            conn.commit()
        except:
            return "Email already exists"

        conn.close()

        return redirect("/login")

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        conn.close()

        # EMAIL NOT FOUND
        if not user:
            return render_template("login.html", error="Email not registered")

        # PASSWORD WRONG
        if not check_password_hash(user[3], password):
            return render_template("login.html", error="Wrong password")

        # LOGIN SUCCESS
        session['user_id'] = user[0]
        session['email'] = user[2]

        return redirect("/")

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():

    session.clear()
    return redirect("/login")


# ---------------- CART PAGE ----------------
@app.route("/cart")
def cart():

    if "user_id" not in session:
        return redirect("/login")

    return render_template("cart.html")


# ---------------- PLACE ORDER ----------------
@app.route("/place_order", methods=["POST"])
def place_order():

    if "user_id" not in session:
        return redirect("/login")

    items = request.form["items"]
    total = request.form["total"]

    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO orders(user_id,items,total) VALUES(?,?,?)",
        (session["user_id"], items, total)
    )

    conn.commit()
    conn.close()

    return render_template("order_success.html")


# ---------------- MY ORDERS ----------------
@app.route("/my_orders")
def my_orders():

    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id,items,total,status,created_at FROM orders WHERE user_id=?",
        (session["user_id"],)
    )

    orders = cursor.fetchall()

    conn.close()

    return render_template("my_orders.html", orders=orders)


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin():

    if "user_id" not in session or session["is_admin"] != 1:
        return redirect("/")

    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT orders.id, users.name, users.email,
           orders.items, orders.total,
           orders.status, orders.created_at
    FROM orders
    JOIN users ON orders.user_id = users.id
    """)

    orders = cursor.fetchall()

    cursor.execute("SELECT id,name,email,is_admin FROM users")
    users = cursor.fetchall()

    conn.close()

    return render_template("admin.html", orders=orders, users=users)


# ---------------- UPDATE ORDER STATUS ----------------
@app.route("/update_status/<int:id>", methods=["POST"])
def update_status(id):

    status = request.form["status"]

    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE orders SET status=? WHERE id=?",
        (status, id)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


# ---------------- PASSWORD RESET ----------------
@app.route("/password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"]

        conn = sqlite3.connect("orders.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        conn.close()

        if user:
            session["reset_user"] = email
            return redirect("/reset_password")

        return "User not found"

    return render_template("password.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():

    if "reset_user" not in session:
        return redirect("/login")

    if request.method == "POST":

        new_password = generate_password_hash(request.form["new_password"])

        conn = sqlite3.connect("orders.db")
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET password=? WHERE email=?",
            (new_password, session["reset_user"])
        )

        conn.commit()
        conn.close()

        session.pop("reset_user")

        return redirect("/login")

    return render_template("reset_password.html")


# ---------------- RUN ----------------
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

