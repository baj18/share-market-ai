"""
Walk-forward backtest with transaction costs.
Run one stock:    python scripts/backtest.py RELIANCE.NS
Run the universe: python scripts/backtest.py --all
Not investment advice.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from config import STOCKS, COMPANY_NAMES, REPORT_DIR
from analyze_stock import load, add_indicators
from forecast_model import build_features, FEATURES

# ---- Tunable assumptions ----
COST_ONE_WAY = 0.0025   # 25 bps per trade (brokerage+STT+slippage). Edit me.
MIN_TRAIN = 250
STEP = 21               # rebalance every ~1 month of trading days
HORIZON = 21            # model predicts the ~1-month-ahead return


def _tech_score_row(row) -> int:
    score = 0
    score += 1 if row["SMA_20"] > row["SMA_50"] else -1
    if not pd.isna(row["SMA_200"]):
        score += 1 if row["Close"] > row["SMA_200"] else -1
    score += 1 if row["MACD"] > row["MACD_signal"] else -1
    if row["RSI"] > 70:
        score -= 1
    elif row["RSI"] < 30:
        score += 1
    return score


def _decided_positions(df: pd.DataFrame):
    n = len(df)
    rebal = list(range(MIN_TRAIN, n, STEP))

    dec_tech = pd.Series(np.nan, index=df.index)
    dec_model = pd.Series(np.nan, index=df.index)

    feat_df = build_features(df).replace([np.inf, -np.inf], np.nan)

    for i in rebal:
        dec_tech.iloc[i] = 1.0 if _tech_score_row(df.iloc[i]) >= 2 else 0.0

        train = feat_df.iloc[:i].copy()
        train["target"] = train["Close"].shift(-HORIZON) / train["Close"] - 1.0
        train = train.dropna(subset=FEATURES + ["target"])
        latest = feat_df[FEATURES].iloc[[i]]
        if len(train) >= 150 and not latest.isna().any(axis=1).iloc[0]:
            model = RandomForestRegressor(
                n_estimators=200, max_depth=6, min_samples_leaf=20,
                random_state=42, n_jobs=-1,
            )
            model.fit(train[FEATURES], train["target"])
            pred = float(model.predict(latest)[0])
            dec_model.iloc[i] = 1.0 if pred > 0 else 0.0
        else:
            dec_model.iloc[i] = 0.0

    return dec_tech.ffill(), dec_model.ffill(), rebal[0]


def _equity(daily_ret: pd.Series, decided: pd.Series, start: int):
    held = decided.shift(1)
    held = held.iloc[start:].fillna(0.0)
    ret = daily_ret.iloc[start:]
    cost = COST_ONE_WAY * held.diff().abs().fillna(held.abs())
    strat = held * ret - cost
    trades = int((held.diff().abs() > 0).sum())
    exposure = float(held.mean())
    return strat, trades, exposure


def _metrics(daily_ret: pd.Series) -> dict:
    r = daily_ret.dropna()
    if len(r) == 0:
        return {"total": 0, "cagr": float("nan"), "vol": float("nan"),
                "sharpe": float("nan"), "maxdd": float("nan"), "equity": r}
    eq = (1 + r).cumprod()
    years = len(r) / 252
    total = eq.iloc[-1] - 1
    cagr = eq.iloc[-1] ** (1 / years) - 1 if eq.iloc[-1] > 0 else float("nan")
    vol = r.std() * np.sqrt(252)
    sharpe = (r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else float("nan")
    maxdd = (eq / eq.cummax() - 1).min()
    return {"total": total, "cagr": cagr, "vol": vol,
            "sharpe": sharpe, "maxdd": maxdd, "equity": eq}


def backtest(ticker: str) -> dict:
    df = add_indicators(load(ticker))
    daily_ret = df["Close"].pct_change()

    dec_tech, dec_model, start = _decided_positions(df)

    tech_ret, tech_trades, tech_exp = _equity(daily_ret, dec_tech, start)
    model_ret, model_trades, model_exp = _equity(daily_ret, dec_model, start)
    bh_ret = daily_ret.iloc[start:].copy()
    bh_ret.iloc[0] = bh_ret.iloc[0] - COST_ONE_WAY

    return {
        "ticker": ticker, "name": COMPANY_NAMES.get(ticker, ticker),
        "tech": {**_metrics(tech_ret), "trades": tech_trades, "exposure": tech_exp},
        "model": {**_metrics(model_ret), "trades": model_trades, "exposure": model_exp},
        "buyhold": {**_metrics(bh_ret), "trades": 1, "exposure": 1.0},
    }


def _print_one(r: dict):
    print(f"\n{r['name']} ({r['ticker']})  -  walk-forward, "
          f"{COST_ONE_WAY*100:.2f}% one-way cost, monthly rebalance")
    print(f"{'Strategy':14s}{'Total':>9}{'CAGR':>8}{'Vol':>8}"
          f"{'Sharpe':>8}{'MaxDD':>8}{'Trades':>8}{'InMkt':>7}")
    print("-" * 78)
    for key, lbl in [("tech", "Technical"), ("model", "ML model"), ("buyhold", "Buy & hold")]:
        m = r[key]
        print(f"{lbl:14s}{m['total']*100:>8.1f}%{m['cagr']*100:>7.1f}%"
              f"{m['vol']*100:>7.1f}%{m['sharpe']:>8.2f}{m['maxdd']*100:>7.1f}%"
              f"{m['trades']:>8}{m['exposure']*100:>6.0f}%")


def _save_outputs(r: dict):
    os.makedirs(REPORT_DIR, exist_ok=True)
    curves = pd.DataFrame({
        "technical": r["tech"]["equity"],
        "ml_model": r["model"]["equity"],
        "buy_hold": r["buyhold"]["equity"],
    })
    csv_path = os.path.join(REPORT_DIR, f"{r['ticker']}_backtest.csv")
    curves.to_csv(csv_path)
    print(f"\nEquity curves -> {csv_path}")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ax = curves.plot(figsize=(9, 5), title=f"{r['name']}: growth of 1 (net of costs)")
        ax.set_ylabel("Equity (x starting capital)")
        png = os.path.join(REPORT_DIR, f"{r['ticker']}_backtest.png")
        plt.tight_layout(); plt.savefig(png); plt.close()
        print(f"Chart        -> {png}")
    except Exception as e:
        print(f"(plot skipped: {e})")


def run_all():
    rows = []
    for t in STOCKS:
        path = os.path.join("data", f"{t}.csv")
        if not os.path.exists(path):
            continue
        try:
            rows.append(backtest(t))
        except Exception as e:
            print(f"  [err] {t}: {e}")
    if not rows:
        print("No data. Run: python scripts/get_stock_data.py")
        return
    tech_beat = sum(1 for r in rows if r["tech"]["cagr"] > r["buyhold"]["cagr"])
    model_beat = sum(1 for r in rows if r["model"]["cagr"] > r["buyhold"]["cagr"])
    n = len(rows)
    print(f"\n{'Stock':26s}{'Tech CAGR':>11}{'ML CAGR':>10}{'B&H CAGR':>11}  Winner")
    print("-" * 74)
    for r in sorted(rows, key=lambda x: x["buyhold"]["cagr"], reverse=True):
        t_c, m_c, b_c = r["tech"]["cagr"], r["model"]["cagr"], r["buyhold"]["cagr"]
        winner = max([("Tech", t_c), ("ML", m_c), ("B&H", b_c)], key=lambda x: x[1])[0]
        print(f"{r['name'][:25]:26s}{t_c*100:>10.1f}%{m_c*100:>9.1f}%"
              f"{b_c*100:>10.1f}%  {winner}")
    print("-" * 74)
    print(f"Beat buy-and-hold (net of costs):  Technical {tech_beat}/{n},  "
          f"ML model {model_beat}/{n}")
    print("\nIf the strategies rarely beat buy-and-hold after costs, that is the "
          "honest, expected result.")


if __name__ == "__main__":
    args = list(sys.argv[1:])
    if "--all" in args:
        run_all()
    else:
        ticker = next((a for a in args if not a.startswith("-")), "RELIANCE.NS")
        r = backtest(ticker)
        _print_one(r)
        _save_outputs(r)