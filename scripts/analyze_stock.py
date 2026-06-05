"""Step 2: Technical indicators + a rule-based signal."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd
import ta

from config import DATA_DIR


def load(ticker: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{ticker}.csv")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Close"])


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"]
    df["SMA_20"] = close.rolling(20).mean()
    df["SMA_50"] = close.rolling(50).mean()
    df["SMA_200"] = close.rolling(200).mean()
    df["RSI"] = ta.momentum.RSIIndicator(close=close, window=14).rsi()
    macd = ta.trend.MACD(close=close)
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    df["Volatility"] = close.pct_change().rolling(20).std() * (252 ** 0.5)
    return df


def technical_signal(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    reasons = []
    score = 0

    if last["SMA_20"] > last["SMA_50"]:
        score += 1; reasons.append("Short-term trend above medium-term (SMA20 > SMA50)")
    else:
        score -= 1; reasons.append("Short-term trend below medium-term (SMA20 < SMA50)")

    if not pd.isna(last["SMA_200"]):
        if last["Close"] > last["SMA_200"]:
            score += 1; reasons.append("Price above 200-day average (long-term uptrend)")
        else:
            score -= 1; reasons.append("Price below 200-day average (long-term downtrend)")

    if last["MACD"] > last["MACD_signal"]:
        score += 1; reasons.append("MACD above its signal line (positive momentum)")
    else:
        score -= 1; reasons.append("MACD below its signal line (negative momentum)")

    rsi = last["RSI"]
    if rsi > 70:
        score -= 1; reasons.append(f"RSI {rsi:.0f}: overbought, chasing is risky")
    elif rsi < 30:
        score += 1; reasons.append(f"RSI {rsi:.0f}: oversold, possible bounce")
    else:
        reasons.append(f"RSI {rsi:.0f}: neutral")

    if score >= 2:
        signal = "Buy / Accumulate"
    elif score <= -2:
        signal = "Avoid / Reduce"
    else:
        signal = "Hold / Watch"

    return {
        "signal": signal, "score": score,
        "rsi": round(float(rsi), 1),
        "close": round(float(last["Close"]), 2),
        "volatility": round(float(last["Volatility"]), 3),
        "reasons": reasons,
    }


if __name__ == "__main__":
    ticker = "RELIANCE.NS"
    df = add_indicators(load(ticker))
    result = technical_signal(df)
    print(f"\n{ticker}")
    print(f"  Close:   ₹{result['close']}")
    print(f"  Signal:  {result['signal']}  (score {result['score']})")
    print(f"  RSI:     {result['rsi']}")
    print("  Why:")
    for r in result["reasons"]:
        print(f"    - {r}")