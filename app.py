from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

DB = "orders.db"


# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect(DB)


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        items TEXT,
        total INTEGER,
        status TEXT DEFAULT 'Pending'
    )
    """)

    # create admin automatically
    cursor.execute("SELECT * FROM users WHERE is_admin=1")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users(name,email,password,is_admin) VALUES(?,?,?,1)",
            ("Admin","admin@email.com",generate_password_hash("admin123"))
        )

    conn.commit()
    conn.close()


init_db()


# ---------------- HOME ----------------
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "home.html",
        name=session["name"],
        admin=session["admin"]
    )


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users(name,email,password) VALUES(?,?,?)",
                (name,email,password)
            )
            conn.commit()

        except:
            return "Email already exists"

        conn.close()

        return redirect("/login")

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        conn.close()

        if user and check_password_hash(user[3], password):

            session["user_id"] = user[0]
            session["name"] = user[1]
            session["admin"] = user[4]

            return redirect("/")

        return "Invalid email or password"

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ---------------- PLACE ORDER ----------------
@app.route("/place_order", methods=["POST"])
def place_order():

    if "user_id" not in session:
        return redirect("/login")

    items = request.form["items"]
    total = request.form["total"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO orders(user_id,items,total) VALUES(?,?,?)",
        (session["user_id"],items,total)
    )

    conn.commit()
    conn.close()

    return "Order placed successfully"


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin():

    if "user_id" not in session or session["admin"] != 1:
        return redirect("/")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT orders.id, users.name, users.email,
    orders.items, orders.total, orders.status
    FROM orders
    JOIN users ON orders.user_id = users.id
    """)

    orders = cursor.fetchall()

    cursor.execute("SELECT id,name,email,is_admin FROM users")

    users = cursor.fetchall()

    conn.close()

    return render_template(
        "admin.html",
        orders=orders,
        users=users
    )


# ---------------- UPDATE ORDER STATUS ----------------
@app.route("/update_status/<int:order_id>", methods=["POST"])
def update_status(order_id):

    new_status = request.form["status"]

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE orders SET status=? WHERE id=?",
        (new_status,order_id)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")


# ---------------- FORGOT PASSWORD ----------------
@app.route("/password", methods=["GET","POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"]

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        conn.close()

        if user:
            session["reset_user"] = email
            return redirect("/reset_password")

        return "User not found"

    return render_template("password.html")


# ---------------- RESET PASSWORD ----------------
@app.route("/reset_password", methods=["GET","POST"])
def reset_password():

    if "reset_user" not in session:
        return redirect("/login")

    if request.method == "POST":

        new_password = generate_password_hash(request.form["password"])

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET password=? WHERE email=?",
            (new_password,session["reset_user"])
        )

        conn.commit()
        conn.close()

        session.pop("reset_user")

        return redirect("/login")

    return render_template("reset_password.html")


# ---------------- RUN ----------------
if __name__ == "__main__":

    port = int(os.environ.get("PORT",10000))

    app.run(host="0.0.0.0", port=port)

