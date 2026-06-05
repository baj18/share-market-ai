"""Streamlit dashboard (dynamic, with plain-English explanations).
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
st.caption("Educational tool only. NOT investment advice. Forecasts are unreliable by nature. "
           "Everything here is a starting point for your own research, never a buy or sell instruction.")

with st.expander("New here? Read this first (1 minute)"):
    st.write(
        "- This tool reads a stock's past prices and recent news and summarises what they suggest. "
        "It cannot predict the future, and it is not financial advice.\n"
        "- A 'Buy' or 'Avoid' label means the *recent patterns* lean that way - markets ignore patterns all the time.\n"
        "- The most honest part is the forecast's 'Edge?' column: it usually says 'no', which means "
        "short-term prediction is basically a coin flip. That is the truth, not a flaw.\n"
        "- Hover the small ? next to any number, and open the 'What does this mean?' boxes under each chart, "
        "for plain-English explanations."
    )


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
    c1.metric("Current price", f"Rs.{a['current_price']}",
              help="The closing price on the most recent trading day, in rupees. "
                   "It is not a live price - it updates when you refresh the data.")
    c2.metric("Technical", a["technical_signal"],
              help="A verdict based only on price patterns and trends - not on the company's "
                   "business. It looks backwards, so it always lags real moves.")
    c3.metric("News", a["news_sentiment"],
              help="The overall mood (positive / neutral / negative) of recent headlines about "
                   "this company. A weak signal: prices often move opposite to the obvious news.")
    c4.metric("Confidence", f"{a['confidence_pct']}%",
              help="How sure the tool is about its own recommendation (0-100). It is capped at 80 "
                   "and lowered when signals disagree. It is NOT the chance of making money.")

    st.subheader(f"Recommendation: {a['recommendation']}")
    with st.expander("What does this mean?"):
        st.write(
            "This is the tool's overall verdict, combining the technical signal, news mood, "
            "the forecast, and (if loaded) fundamentals. Read it as **'where to look first'**, "
            "not as an instruction. 'Buy / Accumulate' means the signals currently lean positive; "
            "'Avoid / Reduce' means they lean negative; 'Hold / Watch' means they're mixed or unclear. "
            "None of these are advice - do your own research before acting."
        )

    fu = a["fundamentals"]
    if fu["score"] is not None:
        st.subheader(f"Fundamentals: {fu['label']} - score {fu['score']:.0f}/100")
        fcols = st.columns(3)
        fcols[0].metric("P/E", f"{fu['pe']:.1f}" if fu['pe'] else "-",
                        help="Price-to-Earnings: how many rupees you pay for each rupee of yearly "
                             "profit. Lower can mean 'cheaper', but it varies hugely by industry, "
                             "so compare like with like.")
        fcols[1].metric("EPS growth", f"{fu['earnings_growth']*100:.0f}%" if fu['earnings_growth'] is not None else "-",
                        help="How fast the company's profit-per-share is growing year over year. "
                             "Higher is generally better.")
        fcols[2].metric("ROE", f"{fu['roe']*100:.0f}%" if fu['roe'] is not None else "-",
                        help="Return on Equity: how efficiently the company turns shareholders' "
                             "money into profit. Higher usually means a better-run business.")
        with st.expander("What does the fundamentals score mean?"):
            st.write(
                "It rates the company on business basics (profit growth, efficiency, debt, "
                "valuation) **relative to the other stocks in your list** - 0 is the weakest, "
                "100 the strongest. It's a rough quality gauge that matters more over months and "
                "years than day to day. Caveat: it compares all stocks together, but a bank and an "
                "IT firm aren't really comparable on P/E, so treat it as a hint, not a score sheet."
            )

    st.subheader("Price & moving averages")
    st.line_chart(df[["Close", "SMA_20", "SMA_50", "SMA_200"]].dropna())
    with st.expander("What does this mean?"):
        st.write(
            "The dark line is the actual price. The others are **moving averages** - the average "
            "price over the last 20, 50, and 200 days - which smooth out daily noise to show the "
            "trend.\n\n"
            "Rough rule of thumb: when the price sits **above** the 200-day line and the shorter "
            "averages are stacked on top, the stock is generally in an **uptrend**. When they're "
            "tangled or the price is below the 200-day line, the trend is weak or down. "
            "Averages lag, so they confirm trends rather than predict them."
        )

    colA, colB = st.columns(2)
    with colA:
        st.subheader("RSI (14)")
        st.line_chart(df[["RSI"]].dropna())
        with st.expander("What does this mean?"):
            st.write(
                "RSI is a 0-100 'speedometer' for momentum. Above **70** = the stock has risen fast "
                "and may be 'overbought' (a pullback is more likely). Below **30** = it's fallen hard "
                "and may be 'oversold' (a bounce is more likely). These are rules of thumb, not "
                "guarantees - a strong stock can stay overbought for weeks."
            )
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
        with st.expander("What does this mean?"):
            st.write(
                "A model's guess for the price change over the next day, week, and month. "
                "**Read the 'Edge?' column first.** It compares the model against a dumb baseline "
                "('tomorrow = today'). If it says **'no'**, or 'Dir acc' (how often it got up-vs-down "
                "right) is near **50%**, the forecast is basically a **coin flip** - ignore that "
                "number. That's the normal, honest result: short-term prices are very hard to predict."
            )

    st.subheader("Why (technical reasons)")
    for r in a["technical_reasons"]:
        st.write(f"- {r}")
    with st.expander("What does this mean?"):
        st.write(
            "The exact conditions that produced the technical verdict above - nothing is hidden. "
            "Each line is one ingredient (trend direction, momentum, overbought/oversold) that "
            "pushed the signal towards Buy, Hold, or Avoid."
        )

    st.subheader("Key risks")
    for r in a["risks"]:
        st.write(f"- {r}")
    with st.expander("What does this mean?"):
        st.write(
            "Things that could go wrong even if the signal looks positive. Every view here comes "
            "with reasons it might be mistaken - markets, news shocks, and changing conditions can "
            "all break any pattern."
        )

    st.info("Reminder: this is a study aid, not advice. The most useful parts are understanding "
            "the trend and the risks - not chasing the forecast.")

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

        with st.expander("What does this mean? (plain English)"):
            st.write(
                "This pretends you actually traded the signals through history and asks: **would you "
                "have beaten simply buying the stock and holding it - after paying to trade?**\n\n"
                "- **Total / CAGR** - the return over the whole period / per year. Bigger is better.\n"
                "- **Sharpe** - return compared to how bumpy the ride was. The single most useful "
                "number; higher is better.\n"
                "- **Max DD** (drawdown) - the worst peak-to-bottom fall you'd have had to stomach. "
                "Less negative is better.\n"
                "- **Trades** - how often it bought/sold. - **In market** - how much of the time it "
                "actually held the stock vs. sat in cash.\n\n"
                "The chart shows the growth of Rs.1 under each strategy. **The bar to beat is the "
                "'Buy & hold' row.** If the active strategies don't beat it after costs - which is "
                "common - that's the honest lesson: beating the market reliably is genuinely hard."
            )

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
