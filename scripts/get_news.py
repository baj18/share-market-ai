"""Step 3: News + sentiment (free Google News fallback + VADER)."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import urllib.parse
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config import NEWSAPI_KEY, COMPANY_NAMES

_analyzer = SentimentIntensityAnalyzer()


def fetch_google_news(query: str, limit: int = 10):
    q = urllib.parse.quote(f"{query} when:14d")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:limit]:
        items.append({
            "title": entry.get("title", ""),
            "description": entry.get("summary", ""),
            "published": entry.get("published", ""),
            "url": entry.get("link", ""),
        })
    return items


def fetch_newsapi(query: str, limit: int = 10):
    from newsapi import NewsApiClient
    client = NewsApiClient(api_key=NEWSAPI_KEY)
    res = client.get_everything(q=query, language="en",
                                sort_by="publishedAt", page_size=limit)
    return [{
        "title": a["title"], "description": a.get("description") or "",
        "published": a.get("publishedAt", ""), "url": a.get("url", ""),
    } for a in res.get("articles", [])]


def get_news(ticker: str, limit: int = 10):
    name = COMPANY_NAMES.get(ticker, ticker.replace(".NS", ""))
    query = f"{name} stock"
    if NEWSAPI_KEY:
        try:
            return fetch_newsapi(query, limit)
        except Exception as e:
            print(f"NewsAPI failed ({e}); using Google News RSS.")
    return fetch_google_news(query, limit)


def score_text(text: str) -> float:
    if not text:
        return 0.0
    return _analyzer.polarity_scores(text)["compound"]


def news_sentiment(ticker: str, limit: int = 10) -> dict:
    articles = get_news(ticker, limit)
    if not articles:
        return {"label": "No recent news", "score": 0.0, "n": 0, "articles": []}
    scored = []
    for a in articles:
        s = score_text(f"{a['title']}. {a['description']}")
        a["sentiment"] = round(s, 3)
        scored.append(s)
    avg = sum(scored) / len(scored)
    label = "Positive" if avg > 0.15 else "Negative" if avg < -0.15 else "Neutral"
    return {"label": label, "score": round(avg, 3), "n": len(scored), "articles": articles}


if __name__ == "__main__":
    result = news_sentiment("RELIANCE.NS")
    print(f"Overall: {result['label']} (avg {result['score']}, {result['n']} articles)\n")
    for a in result["articles"][:5]:
        print(f"  [{a['sentiment']:+.2f}] {a['title']}")