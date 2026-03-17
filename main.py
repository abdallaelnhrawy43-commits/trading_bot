import ccxt
import pandas as pd
import time
import requests
import json
from datetime import datetime, timedelta

# 🔥 حط توكن البوت الجديد هنا
TELEGRAM_TOKEN = "8657297017:AAHXR2ckJVBhykSo7B60EhYcFnVFogezbus"

# 👑 حط الـ chat_id بتاعك هنا
ADMIN_ID = "5199247792"

# 🌐 لينك الموقع (Railway)
BASE_URL = "https://tradingbot.up.railway.app"


def send(chat_id, msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": chat_id, "text": msg}
    )

# ===== Telegram handler =====
last_update_id = None

def handle_messages():
    global last_update_id

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    updates = requests.get(url).json()

    for u in updates.get("result", []):
        try:
            update_id = u["update_id"]
            if last_update_id and update_id <= last_update_id:
                continue
            last_update_id = update_id

            message = u["message"].get("text", "")
            chat_id = str(u["message"]["chat"]["id"])

            users = load_users()

            # 🎁 تسجيل مستخدم جديد + يوم مجاني
            if chat_id not in users:
                users[chat_id] = {
                    "is_paid": False,
                    "trial_start": datetime.now().strftime("%Y-%m-%d")
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

# ===== Users =====
def load_users():
    try:
        with open("users.json") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open("users.json", "w") as f:
        json.dump(data, f, indent=4)

# ===== Check access =====
def can_use(chat_id, user):

    # 👑 الأدمن دايمًا مفتوح
    if chat_id == ADMIN_ID:
        return True

    # 💰 لو مدفوع
    if user.get("is_paid"):
        return True

    # 🎁 يوم مجاني
    start = datetime.strptime(user.get("trial_start"), "%Y-%m-%d")
    if datetime.now() - start < timedelta(days=1):
        return True

    return False

# ===== Analysis =====
def analyze(symbol, exchange):
    ohlcv = exchange.fetch_ohlcv(symbol, '1m', limit=50)
    df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])

    df['ema50'] = df['c'].ewm(span=50).mean()
    df['ema200'] = df['c'].ewm(span=200).mean()

    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    df['avg_vol'] = df['v'].rolling(20).mean()

    return df.iloc[-1]

def strong_signal(data):
    return (
        data['rsi'] < 35 and
        data['ema50'] > data['ema200'] and
        data['v'] > data['avg_vol'] * 1.5
    )

# ===== Main Loop =====
while True:
    try:
        handle_messages()
        users = load_users()

        for chat_id, user in users.items():

            # 🔒 تحقق من السماح
            if not can_use(chat_id, user):
                send(chat_id, "❌ انتهت الفترة التجريبية\nاشترك علشان تكمل 💰")
                continue

            try:
                exchange = ccxt.binance()
                symbols = ['BTC/USDT','ETH/USDT','SOL/USDT']

                for symbol in symbols:
                    try:
                        data = analyze(symbol, exchange)
                        price = data['c']

                        if strong_signal(data):
                            send(chat_id, f"""
🔥 SIGNAL

💰 {symbol}
📈 Price: {price}
""")
                    except:
                        pass

            except Exception as e:
                print("User Error:", e)

        save_users(users)
        time.sleep(5)

    except Exception as e:
        print("Main Error:", e)