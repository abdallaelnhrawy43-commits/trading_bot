import requests
import pandas as pd
import numpy as np
from ai_model import predict_trade

# ================= SETTINGS =================
SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]
TIMEFRAMES = ["5m","15m","1h"]

# ================= MARKET DATA =================
def get_market_data(symbol, interval="5m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()

    df = pd.DataFrame(data)
    df = df[[0,1,2,3,4,5]]
    df.columns = ["time","open","high","low","close","volume"]

    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)

    return df

# ================= RSI =================
def rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================= MACD =================
def macd(df):
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()

    return macd, signal

# ================= TREND =================
def detect_trend(df):
    ema50 = df["close"].ewm(span=50).mean()
    ema200 = df["close"].ewm(span=200).mean()

    if ema50.iloc[-1] > ema200.iloc[-1]:
        return "UP"
    else:
        return "DOWN"

# ================= VOLUME =================
def volume_strength(df):
    avg_volume = df["volume"].rolling(20).mean()
    if df["volume"].iloc[-1] > avg_volume.iloc[-1] * 1.2:
        return "STRONG"
    return "WEAK"

# ================= SMART MONEY =================
def detect_smc(df):
    highs = df["high"].rolling(10).max()
    lows = df["low"].rolling(10).min()

    if df["close"].iloc[-1] > highs.iloc[-2]:
        return "LIQUIDITY_BREAK_UP"
    elif df["close"].iloc[-1] < lows.iloc[-2]:
        return "LIQUIDITY_BREAK_DOWN"
    return "RANGE"

# ================= NEWS FILTER =================
def news_filter():
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
        data = requests.get(url).json()

        titles = [x["title"].lower() for x in data["Data"][:5]]

        danger = ["crash","hack","ban","sec","regulation","lawsuit"]

        for t in titles:
            for k in danger:
                if k in t:
                    return False
        return True
    except:
        return True

# ================= AI SCORE =================
def ai_score(rsi_val, macd_val, signal_val, trend, volume, smc):
    score = 0

    if rsi_val < 30:
        score += 3
    elif rsi_val > 70:
        score -= 3

    if macd_val > signal_val:
        score += 3
    else:
        score -= 3

    if trend == "UP":
        score += 2
    else:
        score -= 2

    if volume == "STRONG":
        score += 2

    if smc == "LIQUIDITY_BREAK_UP":
        score += 3
    elif smc == "LIQUIDITY_BREAK_DOWN":
        score -= 3

    return score

# ================= GENERATE SIGNAL =================
def generate_signal(symbol, interval="5m"):

    df = get_market_data(symbol, interval)

    df["rsi"] = rsi(df)
    macd_line, signal_line = macd(df)

    trend = detect_trend(df)
    volume = volume_strength(df)
    smc = detect_smc(df)

    news_ok = news_filter()

    rsi_val = df["rsi"].iloc[-1]
    macd_val = macd_line.iloc[-1]
    signal_val = signal_line.iloc[-1]

    score = ai_score(rsi_val, macd_val, signal_val, trend, volume, smc)

    if not news_ok:
        return None

    if score >= 4:
        direction = "LONG"
    elif score <= -4:
        direction = "SHORT"
    else:
        return None

    entry = df["close"].iloc[-1]

    tp = entry * (1.03 if direction=="LONG" else 0.97)
    sl = entry * (0.98 if direction=="LONG" else 1.02)

    confidence = min(95, 60 + abs(score)*5)

    # ================= TYPE =================
    if direction == "LONG" and confidence < 80:
        trade_type = "SPOT"
    else:
        trade_type = "FUTURES"

    signal = {
    "pair": symbol,
    "timeframe": interval,   # 👈 الحل هنا
    "type": trade_type,
    "direction": direction,
    "entry": round(entry,2),
    "tp": round(tp,2),
    "sl": round(sl,2),
    "confidence": confidence,
    "trend": trend,
    "volume": volume,
    "smc": smc
}

    # 🔥 AI FILTER
    if not predict_trade(signal):
        return None

    return signal

# ================= BEST SIGNAL =================
def get_best_signal():

    best = None
    best_score = 0

    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:

            s = generate_signal(symbol, tf)

            if s and s["confidence"] > best_score:
                best = s
                best_score = s["confidence"]

    return best