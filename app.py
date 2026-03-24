from flask import Flask, request, render_template, redirect, session
import sqlite3, os, requests, time
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from market_analyzer import get_best_signal

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret")

TOKEN = "8657297017:AAEg2iFQB4CUokip8_70Tn21uhqSHOEbbng"
BASE_URL = "tradingbot-production-78de.up.railway.app"

# ===== DB =====
def db():
    return sqlite3.connect("users.db")

def init_db():
    conn = db()
    c = conn.cursor()
    c.execute("""
CREATE TABLE IF NOT EXISTS users (
    email TEXT,
    password TEXT,
    chat_id TEXT,
    is_paid INTEGER,
    plan TEXT,
    trial_start TEXT,
    trades INTEGER,
    expiry TEXT,
    api_key TEXT,
    api_secret TEXT,
    profit REAL DEFAULT 0,
    trade_amount REAL DEFAULT 10,
    trade_type TEXT DEFAULT 'futures',
    bot_active INTEGER DEFAULT 0
)
""")
    conn.commit()
    conn.close()

init_db()

# ===== TELEGRAM =====
def send(chat_id, text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": chat_id, "text": text})

# ===== SIGNAL FORMAT =====
def format_signal(s):
    return f"""
🔥 {s['pair']}

📊 Type: {'FUTURES' if s['confidence'] > 80 else 'SPOT'}
📈 Direction: {s['direction']}

💰 Entry: {s['entry']}
🎯 TP: {s['tp']}
🛑 SL: {s['sl']}

📊 Confidence: {s['confidence']}%
📉 Trend: {s['trend']}
📦 Volume: {s['volume']}
🧠 Smart Money: {s['smc']}
"""

# ===== PLAN CONTROL =====
def get_interval(plan):
    if plan == "basic":
        return 1800
    elif plan == "pro":
        return 600
    elif plan == "vip":
        return 60
    return 3600

# ===== TRIAL =====
def can_trade(user):
    if user[3] == 1:
        return True

    start = datetime.strptime(user[5], "%Y-%m-%d")

    if datetime.now() - start < timedelta(days=1) and user[6] < 2:
        return True

    return False

# ===== AUTO SIGNAL LOOP =====
def auto_send():
    while True:
        conn = db()
        c = conn.cursor()
        users = c.execute("SELECT * FROM users").fetchall()

        for user in users:
            chat_id = user[2]
            plan = user[4]

            if not chat_id:
                continue

            if not can_trade(user):
                continue

            signal = get_best_signal()

            if signal:
                msg = format_signal(signal)
                send(chat_id, msg)

                c.execute("UPDATE users SET trades = trades + 1 WHERE chat_id=?", (chat_id,))
                conn.commit()

            time.sleep(get_interval(plan))

        conn.close()

# ===== ROUTES =====
@app.route("/")
def home():
    return "🔥 BOT RUNNING"

@app.route("/register", methods=["GET","POST"])
def register():
    chat_id = request.args.get("chat_id") or ""

    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = db()
        c = conn.cursor()

        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (email,password,chat_id,0,"trial",
                   datetime.now().strftime("%Y-%m-%d"),0,None,None,None,0))

        conn.commit()
        conn.close()

        session["user"] = email
        return redirect("/dashboard")

    return render_template("register.html", chat_id=chat_id)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()
        user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if user and check_password_hash(user[1], password):
            session["user"] = email
            return redirect("/dashboard")

        return "❌ خطأ"

    return render_template("login.html")
@app.route("/save-api", methods=["POST"])
def save_api():
    if not session.get("user"):
        return redirect("/login")

    conn = db()
    c = conn.cursor()

    user = c.execute(
        "SELECT plan FROM users WHERE email=?",
        (session["user"],)
    ).fetchone()

    # ❌ مش VIP
    if not user or user[0] != "vip":
        conn.close()
        return "❌ API متاح فقط لباقة VIP"

    # ✅ VIP فقط
    api_key = request.form.get("api_key")
    api_secret = request.form.get("api_secret")

    c.execute("""
    UPDATE users 
    SET api_key=?, api_secret=? 
    WHERE email=?
    """, (api_key, api_secret, session["user"]))

    conn.commit()
    conn.close()

    return "✅ تم ربط الحساب بنجاح"

@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect("/login")

    conn = db()
    c = conn.cursor()
    user = c.execute("SELECT * FROM users WHERE email=?", (session["user"],)).fetchone()

    return render_template("dashboard.html",
                           plan=user[4],
                           expiry=user[7])

@app.route("/toggle-bot", methods=["POST"])
def toggle_bot():
    if not session.get("user"):
        return redirect("/login")

    conn = db()
    c = conn.cursor()

    user = c.execute(
        "SELECT plan, bot_active FROM users WHERE email=?",
        (session["user"],)
    ).fetchone()

    # ❌ مش VIP
    if not user or user[0] != "vip":
        conn.close()
        return "❌ الميزة متاحة لـ VIP فقط"

    new_status = 0 if user[1] == 1 else 1

    c.execute("""
    UPDATE users SET bot_active=? WHERE email=?
    """, (new_status, session["user"]))

    conn.commit()
    conn.close()

    return "🟢 تم تشغيل البوت" if new_status == 1 else "🔴 تم إيقاف البوت"

# ===== WEBHOOK =====
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        chat_id = str(data["message"]["chat"]["id"])
        text = data["message"].get("text")

        conn = db()
        c = conn.cursor()
        user = c.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,)).fetchone()

        if text == "/start":
            link = f"{BASE_URL}/register?chat_id={chat_id}"
            send(chat_id, f"🚀 سجل هنا:\n{link}")

        conn.close()

    return "ok"

# ===== START =====
if __name__ == "__main__":
    import threading
    threading.Thread(target=auto_send).start()

    app.run(host="0.0.0.0", port=8080)