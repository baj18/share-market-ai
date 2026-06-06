"""Prediction check page -- was the model actually right? (auto-added to sidebar)
Educational tool. Not investment advice.
"""

import os
import sys
import streamlit as st

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "..", "..", "scripts"))
sys.path.insert(0, os.path.join(_here, "..", ".."))

from config import STOCKS, COMPANY_NAMES
import tracker

st.set_page_config(page_title="Prediction check", layout="wide")
st.title("Was the prediction correct?")
st.caption("Hold the model accountable: see how often its forecasts actually came true. "
           "Educational only. NOT investment advice.")

with st.expander("How this works (read me)"):
    st.write(
        "**Check on past data (instant):** the model is sent 'back in time' to several past dates, "
        "allowed to see only the data it would have had then, and made to predict. We compare each "
        "prediction to what really happened next. You get an honest scorecard right now.\n\n"
        "**Track live predictions:** logs today's forecast and grades it later, once enough days "
        "pass. More intuitive, but you have to wait - and on the deployed (cloud) version the saved "
        "log can reset when the app restarts, so it's most reliable when you run the app on your "
        "own computer.\n\n"
        "The key number is **direction accuracy** vs. the **dumb baseline**. If they're close, the "
        "model isn't really predicting - which, for short-term prices, is the normal honest result."
    )


@st.cache_data(show_spinner=False, ttl=3600)
def ensure_data(tkr):
    return tracker._get_df(tkr, fetch=True) is not None


@st.cache_data(show_spinner=False, ttl=3600)
def _verify(tkr, horizon):
    return tracker.verify_history(tkr, horizon_days=horizon)


mode = st.radio("Choose a mode", ["Check on past data (instant)", "Track live predictions (local)"])

if mode == "Check on past data (instant)":
    ticker = st.selectbox("Stock", STOCKS, format_func=lambda t: f"{COMPANY_NAMES.get(t, t)} ({t})")
    hlabel = st.selectbox("Forecast horizon", ["1 month", "1 week"])
    horizon = 21 if hlabel == "1 month" else 5

    if st.button("Check accuracy", type="primary"):
        with st.spinner("Fetching data..."):
            ok = ensure_data(ticker)
        if not ok:
            st.error("Could not fetch data (Yahoo may be rate-limiting). Try again shortly.")
            st.stop()
        with st.spinner("Re-running the model at past dates..."):
            res = _verify(ticker, horizon)
        if "error" in res:
            st.error(f"Could not evaluate: {res['error']}")
            st.stop()

        c1, c2, c3 = st.columns(3)
        c1.metric("Direction correct", f"{res['hit_rate']:.0%}",
                  help="How often the model called up-vs-down correctly, across the past dates checked.")
        c2.metric("Dumb baseline", f"{res['naive_acc']:.0%}",
                  help="Accuracy of just always guessing the more common direction. The model has to "
                       "beat THIS to be worth anything.")
        c3.metric("Avg price error", f"{res['mae']:.1%}",
                  help="On average, how far the predicted price was from the real price.")

        if res["hit_rate"] > res["naive_acc"] + 0.05:
            st.success("The model beat the dumb baseline over this sample - a (rare) sign of some edge. "
                       "Treat cautiously: it can still be luck on a small sample.")
        else:
            st.info("The model did NOT meaningfully beat the dumb baseline - the normal, honest "
                    "result. Short-term price prediction is close to a coin flip.")

        st.subheader(f"Each past prediction ({res['n']} checks)")
        st.dataframe(res["table"], use_container_width=True)
        with st.expander("How to read this table"):
            st.write(
                "Each row is one prediction the model would have made on that date. "
                "'Predicted move' vs 'Actual move' shows the guess against reality; "
                "'Direction right?' is the simple win/lose. A few rights in a row are easy to get by "
                "luck - what matters is the overall rate next to the baseline above."
            )

else:
    st.warning("Live tracking saves a file. It works well on your own computer, but on the deployed "
               "cloud app the file can reset when the app restarts.")
    ticker = st.selectbox("Stock", STOCKS, format_func=lambda t: f"{COMPANY_NAMES.get(t, t)} ({t})")

    if st.button("Log today's prediction for this stock", type="primary"):
        with st.spinner("Computing and logging..."):
            tracker._get_df(ticker, fetch=True)
            added = tracker.log_prediction(ticker)
        if added:
            st.success(f"Logged {added} prediction(s) for {COMPANY_NAMES.get(ticker, ticker)}. "
                       "Come back after the horizon passes to see if it was right.")
        else:
            st.info("Already logged today for this stock (no duplicates added).")

    st.subheader("Your logged predictions")
    with st.spinner("Checking which have matured..."):
        res = tracker.evaluate_log(fetch=True)
    if res.get("empty"):
        st.write("Nothing logged yet. Log a prediction above to start your track record.")
    else:
        if res["hit_rate"] is not None:
            st.metric("Direction correct (matured only)", f"{res['hit_rate']:.0%}",
                      help="Among predictions whose horizon has passed, how often the direction was right.")
        st.caption(f"{res['n_matured']} of {res['n_total']} predictions have matured "
                   "(enough days passed to grade them).")
        st.dataframe(res["table"], use_container_width=True)
        with st.expander("What do the statuses mean?"):
            st.write(
                "- **pending** - not enough trading days have passed yet to grade it; check back later.\n"
                "- **matured** - the horizon has passed, so it's graded against the real price.\n\n"
                "Build up a dozen-plus matured predictions before reading much into the accuracy - a "
                "handful can swing wildly by luck."
            )
