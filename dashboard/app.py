"""Streamlit dashboard (dynamic / self-fetching).
Educational tool. Not investment advice.
"""

import os
import sys
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import STOCKS, COMPANY_NAMES
from analyze_stock import load, add_indicators
from expert_summary import assess

st.set_page_config(page_title="Share Market Analysis", layout="wide")
st.title("Share Market Analysis & Forecasting")
st.caption("Educational tool only. NOT investment advice. Forecasts are unreliable by nature.")


@st.cache_data(show_spinner=False, ttl=3600)
def ensure_data(tkr: str) -> bool:
    from get_stock_data import download_one
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", f"{tkr}.csv")
    try:
        df = download_one(tkr)
        if df is not None and not df.empty:
            df.to_csv(path)
            return True
    except Exception:
        pass
    return os.path.exists(path)


@st.cache_data(show_spinner=False, ttl=86400)
def ensure_fundamentals() -> bool:
    from get_fundamentals import build_table, load_table
    if load_table() is not None:
        return True
    try:
        build_table()
        return True
    except Exception:
        return False


@st.cache_data(show_spinner=False)
def _run_backtest(tkr: str):
    from backtest import backtest
    return backtest(tkr)


ticker = st.selectbox("Stock", STOCKS, format_func=lambda t: f"{COMPANY_NAMES.get(t, t)} ({t})")
col1, col2 = st.columns(2)
fetch_news = col1.checkbox("Live news sentiment (slower)", value=True)
use_fund = col2.checkbox("Include fundamentals (fetches all stocks once, slow)", value=False)

if st.button("Refresh latest data"):
    st.cache_data.clear()
    st.rerun()

if st.button("Analyse", type="primary"):
    with st.spinner("Fetching latest market data..."):
        ok = ensure_data(ticker)
    if not ok:
        st.error("Could not fetch data for this stock (Yahoo may be rate-limiting). "
                 "Try again in a minute or pick another stock.")
        st.stop()

    if use_fund:
        with st.spinner("Loading fundamentals for the universe (one-time)..."):
            ensure_fundamentals()

    with st.spinner("Crunching..."):
        df = add_indicators(load(ticker))
        a = assess(ticker, with_news=fetch_news)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current price", f"Rs.{a['current_price']}")
    c2.metric("Technical", a["technical_signal"])
    c3.metric("News", a["news_sentiment"])
    c4.metric("Confidence", f"{a['confidence_pct']}%")

    st.subheader(f"Recommendation: {a['recommendation']}")

    fu = a["fundamentals"]
    if fu["score"] is not None:
        st.subheader(f"Fundamentals: {fu['label']} - score {fu['score']:.0f}/100")
        fcols = st.columns(3)
        fcols[0].metric("P/E", f"{fu['pe']:.1f}" if fu['pe'] else "-")
        fcols[1].metric("EPS growth", f"{fu['earnings_growth']*100:.0f}%" if fu['earnings_growth'] is not None else "-")
        fcols[2].metric("ROE", f"{fu['roe']*100:.0f}%" if fu['roe'] is not None else "-")

    st.subheader("Price & moving averages")
    st.line_chart(df[["Close", "SMA_20", "SMA_50", "SMA_200"]].dropna())

    colA, colB = st.columns(2)
    with colA:
        st.subheader("RSI (14)")
        st.line_chart(df[["RSI"]].dropna())
    with colB:
        st.subheader("Forecast by horizon")
        rows = []
        for h, v in a["forecast"].items():
            if "error" in v:
                rows.append({"Horizon": h, "Expected": v["error"], "Edge?": "-"})
            else:
                rows.append({
                    "Horizon": h,
                    "Expected": f"{v['expected_return_pct']:+.2f}% (Rs.{v['target_price']})",
                    "Dir acc": f"{v['direction_accuracy']:.0%}",
                    "Edge?": "yes" if v["beats_naive"] else "no",
                })
        st.table(pd.DataFrame(rows))

    st.subheader("Why (technical reasons)")
    for r in a["technical_reasons"]:
        st.write(f"- {r}")

    st.subheader("Key risks")
    for r in a["risks"]:
        st.write(f"- {r}")

    st.info("If a forecast shows 'Edge? no' or direction accuracy near 50%, "
            "treat that horizon as noise - the normal honest result.")

st.divider()
st.subheader("Walk-forward backtest")
st.caption("Did trading these signals beat just buying and holding - after costs? "
           "Retrains the model month by month, so it takes a little while.")

if st.checkbox("Run backtest for the selected stock (slow)"):
    with st.spinner("Fetching data..."):
        ok = ensure_data(ticker)
    if not ok:
        st.warning("Could not fetch data for this stock right now.")
    else:
        with st.spinner("Backtesting (retraining month by month)..."):
            r = _run_backtest(ticker)

        rows = []
        for key, lbl in [("tech", "Technical"), ("model", "ML model"), ("buyhold", "Buy & hold")]:
            m = r[key]
            rows.append({
                "Strategy": lbl,
                "Total": f"{m['total']*100:.1f}%",
                "CAGR": f"{m['cagr']*100:.1f}%",
                "Sharpe": f"{m['sharpe']:.2f}",
                "Max DD": f"{m['maxdd']*100:.1f}%",
                "Trades": m["trades"],
                "In market": f"{m['exposure']*100:.0f}%",
            })
        st.table(pd.DataFrame(rows))

        curves = pd.DataFrame({
            "Technical": r["tech"]["equity"],
            "ML model": r["model"]["equity"],
            "Buy & hold": r["buyhold"]["equity"],
        })
        st.line_chart(curves)

        bh = r["buyhold"]["cagr"]
        beat = [lbl for key, lbl in [("tech", "Technical"), ("model", "ML model")]
                if r[key]["cagr"] > bh]
        if beat:
            st.success(f"Beat buy-and-hold on CAGR (net of costs): {', '.join(beat)}")
        else:
            st.info("Neither active strategy beat buy-and-hold after costs - "
                    "the common, honest result. Edges are rare and costs are real.")

st.divider()
st.caption("Data via Yahoo Finance. Educational project. Not investment advice. Do your own research.")