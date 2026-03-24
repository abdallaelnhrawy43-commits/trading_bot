import time
import sqlite3
from market_analyzer import get_best_signal
import requests

TOKEN = "8657297017:AAEg2iFQB4CUokip8_70Tn21uhqSHOEbbng"

def send(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

def db():
    return sqlite3.connect("users.db")

def get_users():
    conn = db()
    c = conn.cursor()

    users = c.execute("""
    SELECT chat_id, api_key, api_secret, trade_amount, trade_type 
    FROM users 
    WHERE is_paid=1 
    AND plan='vip'
    AND bot_active=1
    AND api_key IS NOT NULL
    """).fetchall()

    conn.close()
    return users

def format_signal(signal):
    return f"""
🔥 {signal['pair']}

📊 Type: {signal['type']}
📈 Direction: {signal['direction']}

💰 Entry: {signal['entry']}
🎯 TP: {signal['tp']}
🛑 SL: {signal['sl']}

📊 Confidence: {signal['confidence']}%
📈 Trend: {signal['trend']}
📦 Volume: {signal['volume']}
🧠 Smart Money: {signal['smc']}
"""

def run():
    last_basic = 0
    last_pro = 0

    while True:
        print("🔥 شغال بيدور على صفقات...")
        try:
            signal = get_best_signal()
            print("Signal:", signal)

            if signal:
                users = get_users()

                for chat_id, plan in users:

                    now = time.time()

                    # BASIC
                    if plan == "basic" and now - last_basic > 1800:
                        send(chat_id, format_signal(signal))
                        last_basic = now

                    # PRO
                    elif plan == "pro" and now - last_pro > 600:
                        send(chat_id, format_signal(signal))
                        last_pro = now

                    # VIP
                    elif plan == "vip":
                        send(chat_id, format_signal(signal))

            time.sleep(60)

        except Exception as e:
            print("ERROR:", e)
            time.sleep(10)

if __name__ == "__main__":
    run()