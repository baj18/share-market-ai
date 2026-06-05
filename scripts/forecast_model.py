"""Step 4: Forecasting (predicts forward returns, checks for real edge)."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from config import DATA_DIR, HORIZONS
from analyze_stock import load, add_indicators


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = add_indicators(df).copy()
    df["ret_1"] = df["Close"].pct_change(1)
    df["ret_5"] = df["Close"].pct_change(5)
    df["ret_10"] = df["Close"].pct_change(10)
    df["sma_ratio"] = df["SMA_20"] / df["SMA_50"]
    df["px_vs_sma200"] = df["Close"] / df["SMA_200"]
    df["vol_change"] = df["Volume"].pct_change(5)
    return df


FEATURES = ["ret_1", "ret_5", "ret_10", "RSI", "MACD",
            "sma_ratio", "px_vs_sma200", "Volatility", "vol_change"]


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    """Replace inf with NaN so they can be dropped/handled, never fed to sklearn."""
    return frame.replace([np.inf, -np.inf], np.nan)


def forecast(ticker: str) -> dict:
    df = _clean(build_features(load(ticker)))
    out = {"ticker": ticker, "current_price": round(float(df["Close"].iloc[-1]), 2),
           "horizons": {}}

    # Build the prediction row from the most recent FULLY-VALID set of features.
    valid_feat = df[FEATURES].dropna()
    if valid_feat.empty:
        for name in HORIZONS:
            out["horizons"][name] = {"error": "no valid feature rows"}
        return out
    latest = valid_feat.iloc[[-1]]

    for name, h in HORIZONS.items():
        d = df.copy()
        d["target"] = d["Close"].shift(-h) / d["Close"] - 1.0
        d = _clean(d).dropna(subset=FEATURES + ["target"])
        if len(d) < 250:
            out["horizons"][name] = {"error": "not enough history"}
            continue

        X, y = d[FEATURES], d["target"]
        split = int(len(d) * 0.8)
        X_tr, X_te = X.iloc[:split], X.iloc[split:]
        y_tr, y_te = y.iloc[:split], y.iloc[split:]

        model = RandomForestRegressor(
            n_estimators=300, max_depth=6, min_samples_leaf=20,
            random_state=42, n_jobs=-1,
        )
        model.fit(X_tr, y_tr)

        pred_te = model.predict(X_te)
        model_mae = mean_absolute_error(y_te, pred_te)
        naive_mae = mean_absolute_error(y_te, np.zeros_like(y_te))
        dir_acc = float((np.sign(pred_te) == np.sign(y_te.values)).mean())

        exp_ret = float(model.predict(latest)[0])
        cur = out["current_price"]

        out["horizons"][name] = {
            "expected_return_pct": round(exp_ret * 100, 2),
            "target_price": round(cur * (1 + exp_ret), 2),
            "direction_accuracy": round(dir_acc, 3),
            "beats_naive": bool(model_mae < naive_mae),
            "model_mae": round(model_mae, 4),
            "naive_mae": round(naive_mae, 4),
        }
    return out


if __name__ == "__main__":
    r = forecast("RELIANCE.NS")
    print(f"\n{r['ticker']}  (current Rs.{r['current_price']})")
    for name, h in r["horizons"].items():
        if "error" in h:
            print(f"  {name}: {h['error']}"); continue
        edge = "has edge over naive" if h["beats_naive"] else "NO edge over naive"
        print(f"  {name:8s}: {h['expected_return_pct']:+.2f}% -> Rs.{h['target_price']} "
              f"| dir acc {h['direction_accuracy']:.0%} | {edge}")
    print("\nReminder: if 'NO edge over naive' or dir acc ~50%, the forecast is noise.")