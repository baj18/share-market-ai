"""
Central configuration for the project.
Edit your stock universe and settings here so every script stays in sync.
"""

# ---- Stock universe (NSE tickers must end in ".NS" for Yahoo Finance) ----
STOCKS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "KOTAKBANK.NS",
    "HINDUNILVR.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "ASIANPAINT.NS", "WIPRO.NS", "TATAMOTORS.NS", "ADANIENT.NS",
]

COMPANY_NAMES = {
    "RELIANCE.NS": "Reliance Industries",
    "TCS.NS": "Tata Consultancy Services",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "SBIN.NS": "State Bank of India",
    "BHARTIARTL.NS": "Bharti Airtel",
    "ITC.NS": "ITC Limited",
    "LT.NS": "Larsen & Toubro",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "AXISBANK.NS": "Axis Bank",
    "BAJFINANCE.NS": "Bajaj Finance",
    "MARUTI.NS": "Maruti Suzuki",
    "SUNPHARMA.NS": "Sun Pharmaceutical",
    "TITAN.NS": "Titan Company",
    "ASIANPAINT.NS": "Asian Paints",
    "WIPRO.NS": "Wipro",
    "TATAMOTORS.NS": "Tata Motors",
    "ADANIENT.NS": "Adani Enterprises",
}

# ---- Data settings ----
HISTORY_PERIOD = "3y"
INTERVAL = "1d"
DATA_DIR = "data"
MODEL_DIR = "models"
REPORT_DIR = "reports"

# ---- Forecast horizons (in trading days) ----
HORIZONS = {"1_day": 1, "1_week": 5, "1_month": 21}

# ---- News ----
# Get a free key at https://newsapi.org . Leave as "" to use free Google News.
NEWSAPI_KEY = ""