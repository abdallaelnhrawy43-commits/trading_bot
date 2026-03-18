import ccxt
import pandas as pd
import time
import requests
import json
from datetime import datetime, timedelta

TELEGRAM_TOKEN = "8657297017:AAEg2iFQB4CUokip8_70Tn21uhqSHOEbbng"
ADMIN_ID = "5199247792"
BASE_URL = "https://tradingbot-production-78de.up.railway.app"

def send(chat_id, msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": chat_id, "text": msg}
    )

last_update_id = None

def handle_messages():
    global last_update_id

    updates = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates").json()

    for u in updates.get("result", []):
        try:
            update_id = u["update_id"]
            if last_update_id and update_id <= last_update_id:
                continue
            last_update_id = update_id

            message = u["message"].get("text", "")
            chat_id = str(u["message"]["chat"]["id"])

            users = load_users()

            if chat_id not in users:
                users[chat_id] = {
                    "is_paid": False,
                    "trial_start": datetime.now().strftime("%Y-%m-%d"),
                    "amount": 50,
                    "risk": 0.02,
                    "mode": "future",
                    "history": []
                }
                save_users(users)

            if message == "/start":
                link = f"{BASE_URL}/register?chat_id={chat_id}"

                send(chat_id, f"""
🚀 AI Crypto Trader

🎁 عندك يوم مجاني للتجربة!

👇 سجل من هنا:
{link}
""")

        except:
            pass

def load_users():
    try:
        with open("users.json") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open("users.json", "w") as f:
        json.dump(data, f, indent=4)

def can_use(chat_id, user):
    if chat_id == ADMIN_ID:
        return True

    if user.get("is_paid"):
        return True

    start = datetime.strptime(user.get("trial_start"), "%Y-%m-%d")
    if datetime.now() - start < timedelta(days=1):
        return True

    return False

# 🔥 AI اختيار العملات
def get_best_symbols(exchange):
    markets = exchange.load_markets()
    symbols = [s for s in markets if "/USDT" in s]

    scored = []

    for symbol in symbols[:50]:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=20)

            closes = [x[4] for x in ohlcv]
            change = (closes[-1] - closes[0]) / closes[0]

            volume = sum([x[5] for x in ohlcv])

            score = abs(change) * volume
            scored.append((symbol, score))
        except:
            continue

    scored.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in scored[:5]]

# 🔥 تحليل احترافي
def analyze(symbol, exchange):
    tf = exchange.fetch_ohlcv(symbol, '5m', limit=100)
    df = pd.DataFrame(tf, columns=['t','o','h','l','c','v'])

    ema_short = df['c'].ewm(span=10).mean().iloc[-1]
    ema_long = df['c'].ewm(span=30).mean().iloc[-1]

    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = rsi.iloc[-1]

    avg_vol = df['v'].rolling(20).mean().iloc[-1]
    vol = df['v'].iloc[-1]

    high = df['h'].rolling(20).max().iloc[-2]
    price = df['c'].iloc[-1]

    signal = (
        ema_short > ema_long and
        rsi_val < 60 and
        vol > avg_vol * 1.5 and
        price > high
    )

    return signal, price

# 🔥 خروج ذكي
def exit_logic(entry, current):
    if current < entry * 0.98:
        return "SL"

    if current > entry * 1.03:
        return "TP"

    return None

# 🔥 تعلم + مخاطرة ذكية
def adjust_risk(user):
    history = user.get("history", [])

    if len(history) < 3:
        return 0.02

    avg = sum(history) / len(history)

    if avg > 0:
        return min(0.05, user.get("risk",0.02) + 0.01)
    else:
        return max(0.01, user.get("risk",0.02) - 0.01)

print("Bot is running...")

while True:
    try:
        handle_messages()
        users = load_users()

        for chat_id, user in users.items():

            if not can_use(chat_id, user):
                send(chat_id, "❌ انتهت الفترة التجريبية\nاشترك علشان تكمل 💰")
                continue

            try:
                exchange = ccxt.binance({
                    "options": {"defaultType": "future"}
                })

                symbols = get_best_symbols(exchange)

                for symbol in symbols:
                    try:
                        signal, price = analyze(symbol, exchange)

                        if signal:
                            risk = adjust_risk(user)
                            amount = (user["amount"] * risk) / price

                            send(chat_id, f"🚀 دخول صفقة {symbol}\nPrice: {price}")

                            entry = price

                            while True:
                                current = exchange.fetch_ticker(symbol)["last"]

                                decision = exit_logic(entry, current)

                                if decision == "SL":
                                    send(chat_id, f"❌ Stop Loss {symbol}")
                                    user["history"].append(-1)
                                    break

                                if decision == "TP":
                                    profit = (current-entry)/entry*100
                                    send(chat_id, f"💰 Profit {profit:.2f}% {symbol}")

                                    user["amount"] += user["amount"] * (profit/100)
                                    user["history"].append(profit)
                                    break

                                time.sleep(3)

                    except Exception as e:
                        print("Symbol Error:", e)

            except Exception as e:
                print("User Error:", e)

        save_users(users)
        time.sleep(5)

    except Exception as e:
        print("Main Error:", e)