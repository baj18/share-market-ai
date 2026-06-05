"""Step 1: Collect stock market data (with the yfinance MultiIndex fix)."""

import os
import time
import pandas as pd
import yfinance as yf

from config import STOCKS, HISTORY_PERIOD, INTERVAL, DATA_DIR


def download_one(ticker: str):
    df = yf.download(
        ticker, period=HISTORY_PERIOD, interval=INTERVAL,
        auto_adjust=True, progress=False,
    )
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index.name = "Date"
    return df


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    ok, failed = [], []
    for ticker in STOCKS:
        try:
            df = download_one(ticker)
            if df is None:
                failed.append(ticker)
                print(f"  [skip] no data for {ticker}")
                continue
            df.to_csv(os.path.join(DATA_DIR, f"{ticker}.csv"))
            ok.append(ticker)
            print(f"  [ok]   {ticker}: {len(df)} rows")
            time.sleep(0.4)
        except Exception as e:
            failed.append(ticker)
            print(f"  [err]  {ticker}: {e}")
    print(f"\nDone. {len(ok)} saved, {len(failed)} failed.")
    if failed:
        print("Failed:", failed)


if __name__ == "__main__":
    main()