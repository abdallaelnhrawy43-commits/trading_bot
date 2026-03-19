from flask import Flask, request, render_template, redirect, session
import sqlite3, os, requests
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import ccxt
import pandas as pd

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret")

TOKEN = os.environ.get("TOKEN")
BASE_URL = "https://tradingbot-production-78de.up.railway.app"

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
        profit REAL DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ===== TELEGRAM =====
def send(chat_id, text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": chat_id, "text": text})

# ===== HOME =====
@app.route("/")
def home():
    return "🔥 البوت شغال"

# ===== REGISTER =====
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        chat_id = request.args.get("chat_id")

        conn = db()
        c = conn.cursor()
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (email,password,chat_id,0,"trial",
                   datetime.now().strftime("%Y-%m-%d"),0,None,None,None,0))
        conn.commit()
        conn.close()

        session["user"] = email
        return redirect("/dashboard")

    return '''
    <form method="POST">
    <input name="email" placeholder="Email">
    <input name="password" placeholder="Password">
    <button>Register</button>
    </form>
    '''

# ===== LOGIN =====
@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    conn = db()
    c = conn.cursor()
    user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if user and check_password_hash(user[1], password):
        session["user"] = email
        return redirect("/dashboard")

    return "❌ خطأ"

# ===== DASHBOARD =====
@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect("/login")

    conn = db()
    c = conn.cursor()
    user = c.execute("SELECT * FROM users WHERE email=?", (session["user"],)).fetchone()

    return f"""
    <h2>Dashboard</h2>
    <p>Plan: {user[4]}</p>
    <p>Trades: {user[6]}</p>
    <p>Profit: {user[10]}</p>

    <form action="/save-api" method="POST">
    <input name="api_key" placeholder="API KEY">
    <input name="api_secret" placeholder="SECRET">
    <button>ربط Binance</button>
    </form>
    """

# ===== SAVE API =====
@app.route("/save-api", methods=["POST"])
def save_api():
    conn = db()
    c = conn.cursor()

    c.execute("UPDATE users SET api_key=?, api_secret=? WHERE email=?",
              (request.form["api_key"], request.form["api_secret"], session["user"]))

    conn.commit()
    conn.close()

    return "✅ تم الربط"

# ===== PAYMENT CALLBACK =====
@app.route("/paymob-callback", methods=["POST"])
def paymob():
    data = request.json

    if data["obj"]["success"]:
        email = data["obj"]["order"]["shipping_data"]["email"]

        conn = db()
        c = conn.cursor()

        expiry = (datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d")
        c.execute("UPDATE users SET is_paid=1, plan='VIP', expiry=? WHERE email=?",
                  (expiry,email))

        user = c.execute("SELECT chat_id FROM users WHERE email=?", (email,)).fetchone()

        conn.commit()
        conn.close()

        if user:
            send(user[0], "🔥 اشتراكك اتفعل!")

    return "OK"

# ===== TRIAL =====
def can_trade(user):
    if user[3] == 1:
        return True

    start = datetime.strptime(user[5], "%Y-%m-%d")

    if datetime.now() - start < timedelta(days=1) and user[6] < 5:
        return True

    return False

# ===== AI SIGNAL =====
def calculate_rsi(df, period=14):
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def generate_signal():
    try:
        exchange = ccxt.binance()

        symbol = "BTC/USDT"
        ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=100)

        df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])

        df['ema20'] = df['c'].ewm(span=20).mean()
        df['ema50'] = df['c'].ewm(span=50).mean()
        df['rsi'] = calculate_rsi(df)

        last = df.iloc[-1]

        if last['rsi'] < 30 and last['ema20'] > last['ema50']:
            return f"🚀 BUY {symbol}"

        if last['rsi'] > 70 and last['ema20'] < last['ema50']:
            return f"🔻 SELL {symbol}"

        return "⏳ لا يوجد فرصة حالياً"

    except:
        return "⚠️ خطأ في التحليل"

# ===== TELEGRAM =====
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
            send(chat_id, f"🚀 سجل من هنا:\n{link}")

        elif user:
            if not can_trade(user):
                send(chat_id, "❌ انتهت التجربة")
            else:
                signal = generate_signal()
                send(chat_id, signal)

                c.execute("UPDATE users SET trades = trades + 1 WHERE chat_id=?", (chat_id,))
                conn.commit()

        conn.close()

    return "ok"
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)