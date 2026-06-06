"""
Prediction tracker -- check whether the model's forecasts are actually right.
Run:  python scripts/tracker.py RELIANCE.NS
Not investment advice.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from config import COMPANY_NAMES
from analyze_stock import load
from forecast_model import build_features, FEATURES

MIN_TRAIN = 250
LOG_PATH = os.path.join("data", "predictions.csv")


def _get_df(ticker: str, fetch: bool = False):
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


def verify_history(ticker: str, horizon_days: int = 21,
                   n_checks: int = 12, step: int = 21) -> dict:
    base = _get_df(ticker)
    if base is None:
        return {"error": "no data"}
    df = build_features(base).replace([np.inf, -np.inf], np.nan)
    n = len(df)
    last_known = n - 1 - horizon_days
    if last_known < MIN_TRAIN:
        return {"error": "not enough history"}

    picks = list(range(last_known, MIN_TRAIN - 1, -step))[:n_checks][::-1]
    rows = []
    for i in picks:
        train = df.iloc[:i].copy()
        train["target"] = train["Close"].shift(-horizon_days) / train["Close"] - 1.0
        train = train.dropna(subset=FEATURES + ["target"])
        feat = df[FEATURES].iloc[[i]]
        if len(train) < 150 or feat.isna().any(axis=1).iloc[0]:
            continue
        model = RandomForestRegressor(n_estimators=200, max_depth=6,
                                      min_samples_leaf=20, random_state=42, n_jobs=-1)
        model.fit(train[FEATURES], train["target"])
        pred_ret = float(model.predict(feat)[0])

        cur = float(df["Close"].iloc[i])
        actual_price = float(df["Close"].iloc[i + horizon_days])
        actual_ret = actual_price / cur - 1.0
        rows.append({
            "Predicted on": df.index[i].strftime("%Y-%m-%d"),
            "Predicted move": f"{pred_ret*100:+.1f}%",
            "Actual move": f"{actual_ret*100:+.1f}%",
            "Predicted price": round(cur * (1 + pred_ret), 1),
            "Actual price": round(actual_price, 1),
            "Direction right?": "yes" if (pred_ret > 0) == (actual_ret > 0) else "no",
            "_dir": (pred_ret > 0) == (actual_ret > 0),
            "_abs_err": abs(cur * (1 + pred_ret) - actual_price) / actual_price,
            "_up": actual_ret > 0,
        })

    if not rows:
        return {"error": "could not evaluate"}
    table = pd.DataFrame(rows)
    hit = float(table["_dir"].mean())
    base_up = float(table["_up"].mean())
    mae = float(table["_abs_err"].mean())
    naive_acc = max(base_up, 1 - base_up)
    show = table.drop(columns=["_dir", "_abs_err", "_up"])
    return {
        "ticker": ticker, "name": COMPANY_NAMES.get(ticker, ticker),
        "horizon_days": horizon_days, "n": len(table),
        "hit_rate": hit, "naive_acc": naive_acc, "mae": mae, "table": show,
    }


def log_prediction(ticker: str) -> int:
    from forecast_model import forecast
    fc = forecast(ticker)
    today = datetime.now().strftime("%Y-%m-%d")
    existing = load_log()
    added = 0
    new_rows = []
    for name, v in fc["horizons"].items():
        if "expected_return_pct" not in v:
            continue
        dup = (not existing.empty) and (
            (existing["date_made"] == today) & (existing["ticker"] == ticker) &
            (existing["horizon_name"] == name)).any()
        if dup:
            continue
        new_rows.append({
            "date_made": today, "ticker": ticker, "name": COMPANY_NAMES.get(ticker, ticker),
            "horizon_name": name,
            "horizon_days": {"1_day": 1, "1_week": 5, "1_month": 21}.get(name, 21),
            "price_at_pred": fc["current_price"],
            "pred_return_pct": v["expected_return_pct"],
            "pred_price": v["target_price"],
        })
        added += 1
    if new_rows:
        os.makedirs("data", exist_ok=True)
        out = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
        out.to_csv(LOG_PATH, index=False)
    return added


def load_log() -> pd.DataFrame:
    if os.path.exists(LOG_PATH):
        return pd.read_csv(LOG_PATH)
    return pd.DataFrame()


def evaluate_log(fetch: bool = False) -> dict:
    log = load_log()
    if log.empty:
        return {"empty": True}
    hist_cache = {}
    out_rows = []
    for _, r in log.iterrows():
        tk = r["ticker"]
        if tk not in hist_cache:
            hist_cache[tk] = _get_df(tk, fetch)
        hist = hist_cache[tk]
        made = pd.to_datetime(r["date_made"])
        status, actual_price, actual_ret, dir_ok = "pending", None, None, None
        if hist is not None:
            after = hist[hist.index >= made]
            need = int(r["horizon_days"])
            if len(after) > need:
                actual_price = float(after["Close"].iloc[need])
                actual_ret = actual_price / float(r["price_at_pred"]) - 1.0
                dir_ok = (float(r["pred_return_pct"]) > 0) == (actual_ret > 0)
                status = "matured"
        out_rows.append({
            "Made on": r["date_made"], "Stock": r.get("name", tk),
            "Horizon": r["horizon_name"],
            "Predicted": f"{float(r['pred_return_pct']):+.1f}%",
            "Actual": f"{actual_ret*100:+.1f}%" if actual_ret is not None else "-",
            "Direction right?": ("yes" if dir_ok else "no") if dir_ok is not None else "(pending)",
            "Status": status, "_dir": dir_ok,
        })
    table = pd.DataFrame(out_rows)
    matured = table[table["Status"] == "matured"]
    hit = float(matured["_dir"].mean()) if not matured.empty else None
    return {"table": table.drop(columns=["_dir"]),
            "n_total": len(table), "n_matured": len(matured), "hit_rate": hit}


if __name__ == "__main__":
    ticker = next((a for a in sys.argv[1:] if not a.startswith("-")), "RELIANCE.NS")
    res = verify_history(ticker)
    if "error" in res:
        print("Error:", res["error"]); sys.exit()
    print(f"\n{res['name']} ({res['ticker']}) - {res['horizon_days']}-day forecasts, "
          f"checked at {res['n']} past dates")
    print(res["table"].to_string(index=False))
    print(f"\nDirection correct : {res['hit_rate']:.0%}")
    print(f"Dumb baseline     : {res['naive_acc']:.0%}  (always guessing the more common direction)")
    print(f"Avg price error   : {res['mae']:.1%}")
    print("\nIf 'direction correct' is near the baseline or ~50%, the model is "
          "not really predicting - the honest, usual result. Not investment advice.")
