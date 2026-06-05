"""Step 5: Expert-style summary (now with a fundamentals layer)."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import json
import math
from datetime import datetime

from config import COMPANY_NAMES, REPORT_DIR
from analyze_stock import load, add_indicators, technical_signal
from get_news import news_sentiment
from forecast_model import forecast

try:
    from get_fundamentals import get_score as _get_fund_score
except Exception:
    _get_fund_score = None


def _num(x):
    try:
        f = float(x)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def assess(ticker: str, with_news: bool = True) -> dict:
    name = COMPANY_NAMES.get(ticker, ticker.replace(".NS", ""))
    tech = technical_signal(add_indicators(load(ticker)))
    fc = forecast(ticker)
    senti = news_sentiment(ticker) if with_news else {"label": "skipped", "score": 0.0, "n": 0}

    fund_row = _get_fund_score(ticker) if _get_fund_score else None
    fund_score = _num(fund_row.get("fund_score")) if fund_row else None
    fundamentals = {
        "score": fund_score,
        "label": (fund_row.get("fund_label") if fund_row else "No data"),
        "rank": _num(fund_row.get("fund_rank")) if fund_row else None,
        "pe": _num(fund_row.get("pe")) if fund_row else None,
        "earnings_growth": _num(fund_row.get("earnings_growth")) if fund_row else None,
        "roe": _num(fund_row.get("roe")) if fund_row else None,
    }

    tilt = tech["score"]
    tilt += 2 if senti["score"] > 0.15 else -2 if senti["score"] < -0.15 else 0
    month = fc["horizons"].get("1_month", {})
    if month.get("beats_naive") and "expected_return_pct" in month:
        tilt += 1 if month["expected_return_pct"] > 0 else -1

    if fund_score is not None:
        if fund_score >= 66:
            tilt += 2
        elif fund_score >= 50:
            tilt += 1
        elif fund_score <= 33:
            tilt -= 2

    if tilt >= 3:
        rec = "Buy / Accumulate on dips"
    elif tilt <= -3:
        rec = "Avoid / Reduce"
    else:
        rec = "Hold / Watch"

    confidence = 50
    confidence += min(abs(tech["score"]), 3) * 6
    if senti["n"] > 0:
        confidence += 5
    if month.get("beats_naive"):
        confidence += 8
    else:
        confidence -= 5
    if month.get("expected_return_pct", 0) * tech["score"] < 0:
        confidence -= 10
    if fund_score is not None:
        confidence += 5
        if (fund_score - 50) * tech["score"] > 0:
            confidence += 5
        elif (fund_score - 50) * tech["score"] < 0:
            confidence -= 8
    confidence = max(35, min(confidence, 80))

    risks = ["Broad market correction / global risk-off",
             f"Elevated volatility (annualised ~{tech['volatility']:.0%})" if tech["volatility"] > 0.35
             else "Stock-specific news shock",
             "Forecast model is statistical, not causal; regime changes break it"]
    if fund_score is not None and fundamentals["pe"] and fundamentals["pe"] > 40:
        risks.append(f"Rich valuation (P/E ~{fundamentals['pe']:.0f}); little room for disappointment")

    return {
        "ticker": ticker, "name": name,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "current_price": fc["current_price"],
        "technical_signal": tech["signal"], "technical_reasons": tech["reasons"],
        "news_sentiment": senti["label"], "news_count": senti["n"],
        "fundamentals": fundamentals,
        "forecast": fc["horizons"],
        "recommendation": rec, "confidence_pct": confidence,
        "risks": risks,
    }


def render(a: dict) -> str:
    f = a["fundamentals"]
    fund_line = f"{f['label']}"
    if f["score"] is not None:
        rank = f" (rank {int(f['rank'])})" if f["rank"] else ""
        fund_line = f"{f['label']}  score {f['score']:.0f}/100{rank}"

    lines = [
        "=" * 60,
        f"  {a['name']}  ({a['ticker']})",
        f"  Generated: {a['generated']}",
        "=" * 60,
        f"  Current price      : Rs.{a['current_price']}",
        f"  Technical signal   : {a['technical_signal']}",
        f"  News sentiment     : {a['news_sentiment']} ({a['news_count']} articles)",
        f"  Fundamentals       : {fund_line}",
    ]
    if f["pe"] is not None or f["earnings_growth"] is not None or f["roe"] is not None:
        pe = f"P/E {f['pe']:.1f}" if f["pe"] is not None else "P/E -"
        eg = f"EPS growth {f['earnings_growth']*100:.0f}%" if f["earnings_growth"] is not None else "EPS growth -"
        roe = f"ROE {f['roe']*100:.0f}%" if f["roe"] is not None else "ROE -"
        lines.append(f"                       {pe} | {eg} | {roe}")
    lines.append("  Forecast:")
    for h, v in a["forecast"].items():
        if "error" in v:
            lines.append(f"    {h:8s}: {v['error']}"); continue
        edge = "edge" if v["beats_naive"] else "no edge"
        lines.append(f"    {h:8s}: {v['expected_return_pct']:+.2f}% "
                     f"(-> Rs.{v['target_price']}, dir {v['direction_accuracy']:.0%}, {edge})")
    lines += [
        f"  Recommendation     : {a['recommendation']}",
        f"  Confidence         : {a['confidence_pct']}%",
        "  Key risks:",
    ]
    lines += [f"    - {r}" for r in a["risks"]]
    lines += [
        "-" * 60,
        "  NOT INVESTMENT ADVICE. Educational output of a statistical tool.",
        "  Signals lag, forecasts are unreliable, fundamentals are a snapshot,",
        "  and past patterns need not repeat. Do your own research.",
        "=" * 60,
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    os.makedirs(REPORT_DIR, exist_ok=True)
    ticker = "RELIANCE.NS"
    a = assess(ticker)
    text = render(a)
    print(text)
    with open(os.path.join(REPORT_DIR, f"{ticker}_report.txt"), "w") as fh:
        fh.write(text)
    with open(os.path.join(REPORT_DIR, f"{ticker}_report.json"), "w") as fh:
        json.dump(a, fh, indent=2)