"""Universe scan page (auto-added to the sidebar by Streamlit).
Educational tool. Not investment advice.
"""

import os
import sys
import pandas as pd
import streamlit as st

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "..", "..", "scripts"))
sys.path.insert(0, os.path.join(_here, "..", ".."))

from scan import scan_universe

st.set_page_config(page_title="Universe scan", layout="wide")
st.title("Scan the whole universe")
st.caption("Screen every stock at once and rank by a blended technical + fundamental "
           "score. Educational only. NOT investment advice.")

with st.expander("What is this page for?"):
    st.write(
        "Instead of checking stocks one at a time, this ranks your whole list together so you can "
        "spot a few interesting names quickly. Think of it as a **shortlist-maker**: screen wide "
        "here, then open the main page for a deep look at the names that stand out. The ranking is "
        "a starting point, never a buy or sell call."
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _scan():
    return scan_universe(fetch=True)


@st.cache_data(show_spinner=False, ttl=86400)
def _ensure_fundamentals():
    from get_fundamentals import build_table, load_table
    if load_table() is not None:
        return True
    try:
        build_table()
        return True
    except Exception:
        return False


include_fund = st.checkbox("Include fundamentals (fetches all stocks once, slower)", value=False)

c1, c2 = st.columns(2)
go = c1.button("Scan now", type="primary")
if c2.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

if go:
    if include_fund:
        with st.spinner("Building fundamentals for the universe (one-time)..."):
            _ensure_fundamentals()
    with st.spinner("Scanning every stock (fetching data)..."):
        table = _scan()

    if table.empty:
        st.error("Could not fetch data (Yahoo may be rate-limiting). Try again shortly.")
        st.stop()

    signals = sorted(table["Signal"].unique().tolist())
    chosen = st.multiselect("Filter by signal", signals, default=signals)
    view = table[table["Signal"].isin(chosen)]

    st.subheader(f"{len(view)} stocks")
    st.dataframe(view, use_container_width=True)

    with st.expander("What do these columns mean? (plain English)"):
        st.write(
            "- **Price** - most recent closing price, in rupees.\n"
            "- **Signal** - the technical verdict (Buy / Hold / Avoid) from price patterns only.\n"
            "- **Tech score** - how strongly the patterns lean: positive = bullish, negative = bearish.\n"
            "- **RSI** - momentum 'speedometer' (0-100). Above 70 = run up fast; below 30 = beaten down.\n"
            "- **Vol %** - how bumpy the stock is (yearly). Higher = riskier, signals less reliable.\n"
            "- **Fund score** - business quality vs. the rest of the list (0-100), if fundamentals are loaded.\n"
            "- **Screen score** - a simple blend of the technical and fundamental scores used to rank the "
            "list. Higher just means 'screens better than the others here' - **not** a buy call."
        )

    st.subheader("Screen score by stock")
    chart = view.set_index("Stock")["Screen score"].sort_values(ascending=False)
    st.bar_chart(chart)
    with st.expander("How to use this"):
        st.write(
            "Use it to pick a handful of names to study, or to compare sectors at a glance. "
            "Tip: filter to just 'Buy' signals, or sort the table by any column by clicking its "
            "header. Then open the main page for the full picture on a name - charts, forecast, "
            "risks, and the honest backtest. None of this is advice."
        )
else:
    st.write("Click **Scan now** to rank the whole list. "
             "The first scan fetches data for every stock, so it takes a little while.")
