"""
Universe scanner. Run: python scripts/scan.py   (add --fetch for fresh data)
Not investment advice.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import pandas as pd

from config import STOCKS, COMPANY_NAMES
from analyze_stock import load, add_indicators, technical_signal

try:
    from get_fundamentals import get_score as _get_fund_score
except Exception:
    _get_fund_score = None


def _get_df(ticker: str, fetch: bool):
    path = os.path.join("data", f"{ticker}.csv")
    if fetch or not os.path.exists(path):
        try:
            from get_stock_data import download_one
            df = download_one(ticker)
            if df is not None and not df.empty:
                os.makedirs("data", exist_ok=True)
                df.to_csv(path)
                return df
        except Exception:
            pass
    if os.path.exists(path):
        return load(ticker)
    return None


def scan_universe(fetch: bool = False) -> pd.DataFrame:
    rows = []
    for t in STOCKS:
        try:
            df = _get_df(t, fetch)
            if df is None or len(df) < 60:
                continue
            ind = add_indicators(df)
            sig = technical_signal(ind)

            fund = _get_fund_score(t) if _get_fund_score else None
            fs = None
            if fund is not None:
                try:
                    fs = float(fund.get("fund_score"))
                    if np.isnan(fs):
                        fs = None
                except (TypeError, ValueError):
                    fs = None

            tech_norm = (sig["score"] + 4) / 8 * 100
            parts = [tech_norm] + ([fs] if fs is not None else [])
            screen = round(float(np.mean(parts)), 1)

            rows.append({
                "Stock": COMPANY_NAMES.get(t, t),
                "Ticker": t,
                "Price": sig["close"],
                "Signal": sig["signal"],
                "Tech score": sig["score"],
                "RSI": sig["rsi"],
                "Vol %": round(sig["volatility"] * 100, 1),
                "Fund score": round(fs, 1) if fs is not None else None,
                "Screen score": screen,
            })
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Screen score", ascending=False).reset_index(drop=True)
        df.index = df.index + 1
    return df


if __name__ == "__main__":
    fetch = "--fetch" in sys.argv
    table = scan_universe(fetch=fetch)
    if table.empty:
        print("No data. Run: python scripts/get_stock_data.py  (or add --fetch)")
    else:
        with pd.option_context("display.max_rows", None, "display.width", 120):
            print(table.to_string())
        print("\nScreen score blends technical + fundamental. Higher = screens "
              "better vs. this list. Not investment advice.")
