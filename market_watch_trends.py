# trends.py
# Google Trends: 指定キーワード（5ワード）を取得し daily-ish データを保存・プロット
from pytrends.request import TrendReq
import pandas as pd
import matplotlib.pyplot as plt
import time
import sys

KEYWORDS = [
    "Sell my house fast",
    "give car back",
    "Borrow against life insurance",
    "sell my rolex watch",
    "bankruptcy lawyer"
]

def fetch_trends(keywords, timeframe="today 6-m", attempts=3, wait=5):
    py = TrendReq(hl='en-US', tz=360, retries=2, backoff_factor=0.5)
    for i in range(attempts):
        try:
            py.build_payload(keywords, timeframe=timeframe)
            df = py.interest_over_time()
            if df is None or df.empty:
                raise ValueError("No trends data")
            # drop isPartial column if present
            if 'isPartial' in df.columns:
                df = df.drop(columns=['isPartial'])
            return df
        except Exception as e:
            print(f"⚠️ Attempt {i+1} failed: {e}", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("Google Trends fetch failed after attempts")

def save_and_plot(df, keywords):
    # save csv
    df.to_csv("trends_data.csv", index=True)
    # plot
    plt.figure(figsize=(12,6))
    for kw in keywords:
        if kw in df.columns:
            plt.plot(df.index, df[kw], label=kw)
    plt.title("Google Trends (daily) - specified keywords")
    plt.xlabel("Date")
    plt.ylabel("Interest (0-100)")
    plt.legend(loc='upper right')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("trends_graph.png")
    plt.close()
    print("✅ trends_data.csv and trends_graph.png saved")

def main():
    try:
        df = fetch_trends(KEYWORDS, timeframe="today 6-m", attempts=3, wait=5)
    except Exception as e:
        print(f"Error fetching trends: {e}", file=sys.stderr)
        # create an empty placeholder CSV and image indicating no data
        empty = pd.DataFrame()
        empty.to_csv("trends_data.csv")
        # placeholder image
        plt.figure(figsize=(8,4))
        plt.text(0.5, 0.5, "No trends data", ha='center', va='center', fontsize=16)
        plt.axis('off')
        plt.savefig("trends_graph.png")
        plt.close()
        sys.exit(0)

    # If successful, ensure datetime index is fine
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    save_and_plot(df, KEYWORDS)

if __name__ == "__main__":
    main()
