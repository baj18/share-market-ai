"""Universe scan page (auto-added to the sidebar by Streamlit).
Not investment advice.
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

    st.subheader("Screen score by stock")
    chart = view.set_index("Stock")["Screen score"].sort_values(ascending=False)
    st.bar_chart(chart)

    st.info("Screen score blends the technical signal with the fundamental score "
            "(if built). It narrows the field - use the main page for a deep look "
            "at any single name. Higher is only 'better vs. this list', not a buy call.")
else:
    st.write("Click **Scan now** to rank the whole list. "
             "The first scan fetches data for every stock, so it takes a little while.")
