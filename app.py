
from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3, json
from datetime import datetime, timedelta
import os
import requests

TOKEN = os.environ.get("TOKEN")

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text
    })

# 🔐 ADMIN
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
# 💳 PAYMOB
PAYMOB_API_KEY = os.environ.get("PAYMOB_API_KEY")
INTEGRATION_ID = int(os.environ.get("INTEGRATION_ID"))
IFRAME_ID = os.environ.get("IFRAME_ID")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = "secret"

@app.route("/")
def home():
    return "البوت شغال 🔥"

TRIAL_DAYS = 1

# ===== DB =====
def db():
    return sqlite3.connect("users.db")

# ===== INIT =====
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

# ===== ACTIVATE =====
def activate_user(email, plan):
    conn = db()
    c = conn.cursor()
    expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    c.execute("UPDATE users SET is_paid=1, plan=?, expiry=?, status='active' WHERE email=?",
              (plan, expiry, email))
    conn.commit()
    conn.close()

# ===== REGISTER =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()

        c.execute("INSERT INTO users (email,password,is_paid,trial_start,plan,status) VALUES (?,?,?,?,?,?)",
                  (email,password,0,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"basic","active"))

        conn.commit()
        conn.close()

        session["user"] = email
        return redirect("/dashboard")

    return render_template("login.html")

# ===== LOGIN =====
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()
        user = c.execute("SELECT * FROM users WHERE email=? AND password=?",
                         (email,password)).fetchone()

        if user:
            session["user"] = email
            return redirect("/dashboard")

    return render_template("login.html")

# ===== DASHBOARD =====
@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect("/login")

    email = session["user"]

    conn = db()
    c = conn.cursor()
    user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if email == ADMIN_EMAIL:
        return render_template("dashboard.html", plan="ADMIN", expiry="∞")

    if user[3] == 1:
        expiry = datetime.strptime(user[7], "%Y-%m-%d")
        if datetime.now() > expiry:
            return "❌ انتهى الاشتراك"
        return render_template("dashboard.html", plan=user[5], expiry=user[7])

    return render_template("dashboard.html", plan="Trial", expiry="Free")

# ===== PAYMOB PAYMENT =====
@app.route("/create-payment", methods=["POST"])
def create_payment():

    email = session.get("user")
    plan = request.form.get("plan")

    if plan == "basic":
        amount = 1250
    elif plan == "pro":
        amount = 3000
    elif plan == "vip":
        amount = 5000
    else:
        return "Invalid"

    auth = requests.post("https://accept.paymob.com/api/auth/tokens",
                         json={"api_key": PAYMOB_API_KEY}).json()

    token = auth["token"]

    order = requests.post("https://accept.paymob.com/api/ecommerce/orders",
                          json={
                              "auth_token": token,
                              "delivery_needed": False,
                              "amount_cents": amount * 100,
                              "currency": "EGP",
                              "items": [],
                              "shipping_data": {
                                  "email": email,
                                  "first_name": plan
                              }
                          }).json()

    order_id = order["id"]

    payment_key = requests.post("https://accept.paymob.com/api/acceptance/payment_keys",
                                json={
                                    "auth_token": token,
                                    "amount_cents": amount * 100,
                                    "expiration": 3600,
                                    "order_id": order_id,
                                    "billing_data": {
                                        "email": email,
                                        "first_name": plan,
                                        "last_name": "user",
                                        "phone_number": "01000000000",
                                        "city": "Cairo",
                                        "country": "EG"
                                    },
                                    "currency": "EGP",
                                    "integration_id": INTEGRATION_ID
                                }).json()

    final_token = payment_key["token"]

    return redirect(f"https://accept.paymob.com/api/acceptance/iframes/{IFRAME_ID}?payment_token={final_token}")

# ===== WEBHOOK =====
@app.route("/paymob-callback", methods=["POST"])
def paymob_callback():
    data = request.json

    try:
        if data["obj"]["success"]:
            email = data["obj"]["order"]["shipping_data"]["email"]
            plan = data["obj"]["order"]["shipping_data"]["first_name"]

            activate_user(email, plan)
            print("Activated:", email, plan)

    except Exception as e:
        print("Webhook error:", e)

    return "OK"
@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.json

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text")

        if text and text == "/start":
            send_message(chat_id, """🚀 AI Crypto Trader

🎁 معاك يوم مجاني تجربة

📊 إشارات محدودة:
✔ Spot
✔ Futures

💰 ابدأ من هنا:
https://tradingbot-production-78de.up.railway.app

🔥 متفوتش الفرصة
""")

    return "ok"

# ===== ADMIN LOGIN =====
@app.route("/admin-login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        if request.form["email"] == ADMIN_EMAIL and request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")

    return "<form method='POST'><input name='email'><input name='password'><button>Login</button></form>"

# ===== ADMIN PANEL =====
@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/admin-login")

    conn = db()
    c = conn.cursor()
    users = c.execute("SELECT id,email,plan,is_paid,expiry FROM users").fetchall()

    return render_template("admin.html", users=users)

if __name__ == "__main__":
    app.run(debug=True)