"""
Fundamentals layer (current snapshot + cross-sectional scoring).
Run to build the table:   python scripts/get_fundamentals.py --build
Run to see the ranking:   python scripts/get_fundamentals.py
Not investment advice.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import time
import numpy as np
import pandas as pd

from config import STOCKS, COMPANY_NAMES, DATA_DIR

FUND_PATH = os.path.join(DATA_DIR, "fundamentals.csv")

FIELDS = {
    "trailingPE": "pe",
    "pegRatio": "peg",
    "returnOnEquity": "roe",
    "profitMargins": "profit_margin",
    "earningsGrowth": "earnings_growth",
    "revenueGrowth": "revenue_growth",
    "debtToEquity": "debt_to_equity",
    "marketCap": "market_cap",
}

SCORE_METRICS = [
    ("earnings_growth", True),
    ("revenue_growth", True),
    ("roe", True),
    ("profit_margin", True),
    ("pe", False),
    ("peg", False),
    ("debt_to_equity", False),
]


def fetch_one(ticker: str) -> dict:
    import yfinance as yf
    info = yf.Ticker(ticker).info or {}
    row = {"ticker": ticker,
           "name": COMPANY_NAMES.get(ticker, ticker.replace(".NS", ""))}
    for key, col in FIELDS.items():
        row[col] = info.get(key)
    return row


def _pct(series, higher_better: bool):
    s = pd.to_numeric(series, errors="coerce")
    r = s.rank(pct=True)
    return r if higher_better else (1.0 - r)


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["pe", "peg"]:
        if col in df:
            bad = pd.to_numeric(df[col], errors="coerce") <= 0
            df.loc[bad, col] = np.nan
    if "debt_to_equity" in df:
        bad = pd.to_numeric(df["debt_to_equity"], errors="coerce") < 0
        df.loc[bad, "debt_to_equity"] = np.nan

    comp = pd.DataFrame(index=df.index)
    for col, hb in SCORE_METRICS:
        if col in df.columns:
            comp[col] = _pct(df[col], hb)

    df["fund_score"] = (comp.mean(axis=1, skipna=True) * 100).round(1)
    df["fund_rank"] = df["fund_score"].rank(ascending=False, method="min")

    def label(s):
        if pd.isna(s):
            return "No data"
        return "Strong" if s >= 66 else "Weak" if s <= 33 else "Average"
    df["fund_label"] = df["fund_score"].apply(label)
    return df


def build_table() -> pd.DataFrame:
    os.makedirs(DATA_DIR, exist_ok=True)
    rows = []
    for t in STOCKS:
        try:
            rows.append(fetch_one(t))
            print(f"  [ok]   {t}")
            time.sleep(0.4)
        except Exception as e:
            print(f"  [err]  {t}: {e}")
            rows.append({"ticker": t, "name": COMPANY_NAMES.get(t, t)})
    df = compute_scores(pd.DataFrame(rows))
    df.to_csv(FUND_PATH, index=False)
    print(f"\nSaved {len(df)} rows -> {FUND_PATH}")
    return df


def load_table():
    if not os.path.exists(FUND_PATH):
        return None
    return pd.read_csv(FUND_PATH)


def get_score(ticker: str):
    df = load_table()
    if df is None:
        return None
    row = df[df["ticker"] == ticker]
    return None if row.empty else row.iloc[0].to_dict()


def _f(v, pct=False):
    v = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
    if pd.isna(v):
        return "     -"
    return f"{v * 100:5.1f}%" if pct else f"{v:6.1f}"


def rank_universe():
    df = load_table()
    if df is None:
        print("No fundamentals.csv yet. Run: python scripts/get_fundamentals.py --build")
        return
    df = df.sort_values("fund_score", ascending=False, na_position="last")
    print(f"\n{'#':>2}  {'Stock':26s}{'Score':>7}{'P/E':>8}{'EPS gr':>8}{'ROE':>8}  Label")
    print("-" * 72)
    for i, (_, r) in enumerate(df.iterrows(), 1):
        print(f"{i:>2}  {str(r['name'])[:25]:26s}"
              f"{_f(r.get('fund_score')):>7}{_f(r.get('pe')):>8}"
              f"{_f(r.get('earnings_growth'), True):>8}{_f(r.get('roe'), True):>8}"
              f"  {r.get('fund_label', '')}")
    print("\nScore = cross-sectional percentile blend (0-100). Not investment advice.")


if __name__ == "__main__":
    if "--build" in sys.argv:
        build_table()
    else:
        rank_universe()