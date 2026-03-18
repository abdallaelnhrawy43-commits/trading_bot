from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3, json
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = "secret"

TRIAL_DAYS = 1

# ===== DB =====
def db():
    return sqlite3.connect("users.db")

def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT,
        is_paid INTEGER,
        trial_start TEXT,
        plan TEXT,
        status TEXT,
        expiry TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ===== Trial =====
def is_trial_active(trial_start):
    start = datetime.strptime(trial_start, "%Y-%m-%d %H:%M:%S")
    return datetime.now() - start < timedelta(days=TRIAL_DAYS)

# ===== Activate =====
def activate_user(email, plan):
    conn = db()
    c = conn.cursor()

    expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    c.execute("""
    UPDATE users SET is_paid=1, plan=?, expiry=? WHERE email=?
    """, (plan, expiry, email))

    conn.commit()
    conn.close()

# ===== Home =====
@app.route("/")
def home():
    return redirect("/login")

# ===== Register =====
@app.route("/register", methods=["GET", "POST"])
def register():
    chat_id = request.args.get("chat_id")

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()

        user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user:
            return "Email already exists"

        c.execute("""
        INSERT INTO users (email, password, is_paid, trial_start, plan, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            email,
            password,
            0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "basic",
            "active"
        ))

        conn.commit()
        conn.close()

        session["user"] = email
        return redirect("/dashboard")

    return render_template("register.html", chat_id=chat_id)

# ===== Login =====
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()

        user = c.execute("SELECT * FROM users WHERE email=? AND password=?",
                         (email, password)).fetchone()

        if user:
            session["user"] = email
            return redirect("/dashboard")

    return render_template("login.html")

# ===== Dashboard =====
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ===== Save API =====
@app.route("/save-api", methods=["POST"])
def save_api():
    email = session.get("user")

    api_key = request.form["api_key"]
    secret = request.form["secret"]
    amount = float(request.form["amount"])

    conn = db()
    c = conn.cursor()

    user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    user_id = str(user[0])

    try:
        with open("users.json") as f:
            data = json.load(f)
    except:
        data = {}

    data[user_id] = {
        "api_key": api_key,
        "secret": secret,
        "amount": amount,
        "is_paid": True,
        "risk": 0.02,
        "mode": "future"
    }

    with open("users.json", "w") as f:
        json.dump(data, f, indent=4)

    return "✅ تم الربط وبدء التداول"

# ===== Check Access =====
@app.route("/check-access")
def check_access():
    email = session.get("user")

    conn = db()
    c = conn.cursor()
    user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if user[3] == 1:
        return {"status": "paid"}

    if is_trial_active(user[4]):
        return {"status": "trial"}

    return {"status": "expired"}

# ===== Trial Status =====
@app.route("/trial-status")
def trial_status():
    email = session.get("user")

    conn = db()
    c = conn.cursor()
    user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    start = datetime.strptime(user[4], "%Y-%m-%d %H:%M:%S")
    remaining = timedelta(days=TRIAL_DAYS) - (datetime.now() - start)

    if remaining.total_seconds() <= 0:
        return {"msg": "❌ انتهت التجربة"}

    return {"msg": f"🔥 باقي {remaining.seconds//3600} ساعة"}

# ===== Payment (تجريبي) =====
@app.route("/create-payment", methods=["POST"])
def create_payment():
    email = session.get("user")
    plan = request.form["plan"]

    activate_user(email, plan)
    return "💰 تم الاشتراك بنجاح"

# ===== Stats =====
@app.route("/stats")
def stats():
    try:
        with open("users.json") as f:
            users = json.load(f)
    except:
        users = {}

    profits = [u.get("amount", 0) for u in users.values()]

    return jsonify({
        "users": len(users),
        "profit": round(sum(profits), 2)
    })

# ===== API =====
@app.route("/api/data")
def api_data():
    try:
        with open("users.json") as f:
            return json.load(f)
    except:
        return {}
    
    # ===== Admin Login =====
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # 👑 بيانات الادمن (غيرها براحتك)
        if email == "abdallamohamed22@gmail.com" and password == "Abdalla0100@":
            session["admin"] = True
            return redirect("/admin")

    return render_template("login.html")


# ===== Admin Panel =====
@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/admin-login")

    conn = db()
    c = conn.cursor()

    users = c.execute("SELECT * FROM users").fetchall()

    return render_template("admin.html", users=users)


# ===== Activate User =====
@app.route("/activate", methods=["POST"])
def activate():
    email = request.form["email"]
    plan = request.form["plan"]

    activate_user(email, plan)
    return redirect("/admin")


# ===== Deactivate =====
@app.route("/deactivate", methods=["POST"])
def deactivate():
    email = request.form["email"]

    conn = db()
    c = conn.cursor()

    c.execute("UPDATE users SET is_paid=0 WHERE email=?", (email,))
    conn.commit()

    return redirect("/admin")


# ===== Delete =====
@app.route("/delete", methods=["POST"])
def delete():
    email = request.form["email"]

    conn = db()
    c = conn.cursor()

    c.execute("DELETE FROM users WHERE email=?", (email,))
    conn.commit()

    return redirect("/admin")

if __name__ == "__main__":
    app.run()