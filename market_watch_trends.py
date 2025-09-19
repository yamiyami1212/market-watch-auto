#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch Google Trends (pytrends) for keywords listed in data_sources.json
Saves trends_trends.png and trends_data.csv
"""
import json
import time
import sys
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq

def load_config():
    try:
        with open("data_sources.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"google_keywords": ["sell my house fast","give car back","borrow against life insurance","sell my rolex watch","bankruptcy lawyer"]}

cfg = load_config()
KEYWORDS = cfg.get("google_keywords", [])
TIMEFRAME = "today 6-m"  # last 6 months
OUT_PNG = "google_trends_keywords.png"
OUT_CSV = "google_trends.csv"

def fetch_trends(keywords, tries=3, pause=5):
    if not keywords:
        raise ValueError("No keywords provided")
    for attempt in range(1, tries+1):
        try:
            pytrends = TrendReq(hl='en-US', tz=0, retries=2, backoff_factor=0.5, timeout=(10,25))
            pytrends.build_payload(keywords, cat=0, timeframe=TIMEFRAME, geo='', gprop='')
            data = pytrends.interest_over_time()
            if data.empty:
                print("pytrends returned empty DataFrame", flush=True)
            else:
                # drop isPartial column if present
                if 'isPartial' in data.columns:
                    data = data.drop(columns=['isPartial'])
                return data
        except Exception as e:
            print(f"[pytrends] attempt {attempt} failed: {e}", flush=True)
            time.sleep(pause)
    raise RuntimeError("Failed to fetch Google Trends after retries")

def main():
    print("Fetching Google Trends for keywords:", KEYWORDS, flush=True)
    try:
        df = fetch_trends(KEYWORDS)
    except Exception as e:
        print("Google Trends fetch failed:", e, flush=True)
        # write empty csv so workflow doesn't fail to find artifact
        pd.DataFrame().to_csv(OUT_CSV)
        sys.exit(0)

    # resample to daily/monthly as desired - pytrends gives daily for 'today 6-m' usually
    # we'll convert index to datetime and keep as-is (daily). Save CSV and figure.
    df.index = pd.to_datetime(df.index)
    df.to_csv(OUT_CSV, float_format="%.6f")
    print(f"Wrote {OUT_CSV}", flush=True)

    # Plot
    plt.figure(figsize=(12,6))
    for kw in KEYWORDS:
        if kw in df.columns:
            plt.plot(df.index, df[kw], label=kw)
    plt.legend(loc="upper left")
    plt.title("Google Trends (daily) - specified keywords")
    plt.xlabel("Date")
    plt.ylabel("Interest (0-100)")
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    print(f"Wrote {OUT_PNG}", flush=True)

if __name__ == "__main__":
    main()
