import time
import datetime
import os
import sys
import traceback

import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq

KEYWORDS = ["Bitcoin", "Ethereum", "NFT"]

def fetch_trends(keywords, retries=3, sleep_sec=5):
    df = None
    for attempt in range(retries):
        try:
            pytrends = TrendReq(hl='en-US', tz=360, retries=2, backoff_factor=0.1)
            pytrends.build_payload(keywords, timeframe="today 6-m")
            df = pytrends.interest_over_time()
            if df is not None and not df.empty:
                return df
            else:
                print(f"Attempt {attempt+1}: empty result, retrying...")
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            # do not raise; wait and retry
            time.sleep(sleep_sec)
    return None

def save_placeholder_image(path):
    plt.figure(figsize=(10, 6))
    plt.text(0.5, 0.5, "No data", horizontalalignment='center',
             verticalalignment='center', fontsize=24, alpha=0.7)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Saved placeholder image: {path}")

def plot_and_save(df, keywords, path):
    plt.figure(figsize=(10, 6))
    plotted = False
    for kw in keywords:
        if kw in df.columns:
            plt.plot(df.index, df[kw], label=kw)
            plotted = True
    if not plotted:
        # fallback if columns not present
        save_placeholder_image(path)
        return
    plt.legend()
    plt.title("Google Trends: Last 6 Months")
    plt.xlabel("Date")
    plt.ylabel("Search Interest")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Saved graph image: {path}")

def main():
    out_file = "trend.png"
    # ensure old file removed
    if os.path.exists(out_file):
        try:
            os.remove(out_file)
        except Exception:
            pass

    df = fetch_trends(KEYWORDS, retries=3, sleep_sec=5)

    if df is None or df.empty:
        print("Could not fetch Google Trends data. Creating placeholder image.")
        save_placeholder_image(out_file)
    else:
        try:
            # remove 'isPartial' or similar if present
            if 'isPartial' in df.columns:
                df = df.drop(columns=['isPartial'])
            df = df.dropna(how='all')
            plot_and_save(df, KEYWORDS, out_file)
        except Exception as e:
            print("Error while plotting:", e)
            traceback.print_exc()
            save_placeholder_image(out_file)

    # optional: print absolute path
    print("Output file:", os.path.abspath(out_file))

if __name__ == "__main__":
    main()
