import numpy as np

# ================= AI DECISION ENGINE =================

def predict_trade(signal):
    score = 0

    # ===== Confidence =====
    if signal["confidence"] >= 85:
        score += 3
    elif signal["confidence"] >= 75:
        score += 2
    else:
        score -= 2

    # ===== Trend =====
    if signal["trend"] == "UP" and signal["direction"] == "LONG":
        score += 2
    elif signal["trend"] == "DOWN" and signal["direction"] == "SHORT":
        score += 2
    else:
        score -= 2

    # ===== Volume =====
    if signal["volume"] == "STRONG":
        score += 2
    else:
        score -= 1

    # ===== Smart Money =====
    if signal["smc"] == "LIQUIDITY_BREAK_UP" and signal["direction"] == "LONG":
        score += 3
    elif signal["smc"] == "LIQUIDITY_BREAK_DOWN" and signal["direction"] == "SHORT":
        score += 3
    else:
        score -= 2

    # ===== Timeframe Strength =====
    if signal["timeframe"] == "1h":
        score += 2
    elif signal["timeframe"] == "15m":
        score += 1

    # ===== FINAL DECISION =====
    return score >= 5