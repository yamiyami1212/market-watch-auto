# market_watch_trends.py
import time
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq
import sys

# === ここで必ずユーザー指定の5ワードにする ===
KEYWORDS = [
    "sell my house fast",
    "give car back",
    "borrow against life insurance",
    "sell my rolex watch",
    "bankruptcy lawyer"
]

OUT_PNG = "trends_keywords.png"
OUT_CSV = "trends_keywords.csv"

def fetch_trends(keywords, attempts=3, sleep_seconds=5):
    # ヘッダを指定して Google にブロックされにくくする
    pytrends = TrendReq(hl='en-US', tz=360, requests_args={
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/91.0.4472.124 Safari/537.36"
        }
    })

    df = None
    for attempt in range(attempts):
        try:
            print(f"Attempt {attempt+1} to fetch Google Trends...")
            pytrends.build_payload(keywords, timeframe='today 6-m')
            df = pytrends.interest_over_time()
            # interest_over_time returns extra column 'isPartial' sometimes; remove it
            if df is not None and 'isPartial' in df.columns:
                df = df.drop(columns=['isPartial'])
            if df is None or df.empty:
                print("Got empty DataFrame from pytrends.")
                raise RuntimeError("Empty trends data")
            print("✅ Google Trends data fetched.")
            return df
        except Exception as e:
            print(f"⚠️ Attempt {attempt+1} failed: {e}")
            time.sleep(sleep_seconds)
    # 最後までダメなら None を返す
    return None

def plot_trends(df, keywords, out_png):
    plt.figure(figsize=(12,5))
    if df is None or df.empty:
        # No data -> placeholder image
        fig = plt.figure(figsize=(8,4))
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No trends data", ha='center', va='center', fontsize=18)
        ax.set_axis_off()
        fig.suptitle("Google Trends (daily) - specified keywords")
        fig.savefig(out_png, bbox_inches='tight')
        print(f"Saved placeholder image to {out_png}")
        return

    # Ensure index is datetime and daily
    df.index = pd.to_datetime(df.index)
    # Plot each keyword
    for kw in keywords:
        if kw in df.columns:
            plt.plot(df.index, df[kw], label=kw)
        else:
            print(f"Note: keyword '{kw}' not in DataFrame columns")

    plt.legend(loc='upper right', fontsize=8)
    plt.title("Google Trends (daily) - specified keywords")
    plt.xlabel("Date")
    plt.ylabel("Interest (0-100)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_png)
    print(f"Saved trends graph to {out_png}")

def main():
    df = fetch_trends(KEYWORDS)
    # Save raw csv for debugging / archive (if df exists)
    if df is not None and not df.empty:
        try:
            df.to_csv(OUT_CSV)
            print(f"Saved trends CSV to {OUT_CSV}")
        except Exception as e:
            print(f"Could not save CSV: {e}")

    plot_trends(df, KEYWORDS, OUT_PNG)

if __name__ == "__main__":
    main()
