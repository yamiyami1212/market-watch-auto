#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
market_watch_auto.py

Outputs:
 - macro_graph.png       # M2 YoY (left), HY spread (left), VIX (right)
 - macro_data.csv        # combined macro monthly data
 - trends_graph.png      # daily trends for specified keywords
 - trends_data.csv       # trends raw data (daily)
"""

import os
import zipfile
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt

# FRED data
from pandas_datareader import data as pdr

# pytrends
from pytrends.request import TrendReq
import time

# ----------------------------
# Settings (必要ならここを編集)
# ----------------------------
# timeframe: last 12 months to give margin (workflow earlier used 6 months; adjust if you want)
END = pd.Timestamp.today()
START = END - pd.DateOffset(months=12)

# FRED series
FRED_SERIES = {
    "M2": "M2SL",               # M2 money stock
    "HY": "BAMLH0A0HYM2",      # HY spread (BofA) - check if available
    "VIX": "VIXCLS",           # VIX index
}

# Google keywords (指定された 5 ワード)
KEYWORDS = [
    "sell my house fast",
    "give car back",
    "borrow against life insurance",
    "sell my rolex watch",
    "bankruptcy lawyer"
]

# pytrends user-agent / requests args: GitHub Actions 実行では標準 User-Agent を指定しておくと安定
REQUESTS_ARGS = {
    'headers': {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36'
    }
}

# Output filenames
MACRO_PNG = "macro_graph.png"
MACRO_CSV = "macro_data.csv"
TRENDS_PNG = "trends_graph.png"
TRENDS_CSV = "trends_data.csv"

# ----------------------------
# Fetch macro from FRED
# ----------------------------
def fetch_macro(start=START, end=END):
    dfm = pd.DataFrame(index=pd.date_range(start=start, end=end, freq='D'))
    series_data = {}
    for name, code in FRED_SERIES.items():
        try:
            s = pdr.DataReader(code, "fred", start, end)
            s = s.rename(columns={s.columns[0]: name})
            series_data[name] = s
        except Exception as e:
            print(f"⚠️ Failed to fetch {code}: {e}")
    # combine monthly (resample to month-end mean)
    if not series_data:
        return pd.DataFrame()
    combined = pd.concat([series_data[k].resample('M').mean() for k in series_data], axis=1)
    # compute M2 YoY (%) if present
    if "M2" in combined.columns:
        combined["M2_YoY_pct"] = combined["M2"].pct_change(12) * 100
    # HY already in (usually in percent or bps depending on series). We'll assume it's in bps or percent — keep as-is.
    # VIX is levels.
    combined = combined.drop(columns=[c for c in combined.columns if c in ("M2",)])
    return combined

# ----------------------------
# Plot macro
# Left axis: M2_YoY_pct, HY
# Right axis: VIX
# ----------------------------
def plot_macro(df):
    if df.empty:
        print("⚠️ macro df is empty — skipping macro plot")
        return False
    # ensure columns present
    left_cols = []
    if "M2_YoY_pct" in df.columns:
        left_cols.append("M2_YoY_pct")
    if "HY" in df.columns:
        left_cols.append("HY")
    right_col = "VIX" if "VIX" in df.columns else None

    fig, ax1 = plt.subplots(figsize=(12,5))
    for col in left_cols:
        ax1.plot(df.index, df[col], label=col)
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Left axis: M2 YoY (%) / HY Spread (bps or %)")
    ax1.legend(loc='upper left')

    if right_col:
        ax2 = ax1.twinx()
        ax2.plot(df.index, df[right_col], color='tab:orange', linestyle='--', label=right_col)
        ax2.set_ylabel(f"{right_col} (index)")
        ax2.legend(loc='upper right')

    ax1.grid(True)
    plt.title("M2 YoY, HY Spread, VIX")
    plt.tight_layout()
    plt.savefig(MACRO_PNG)
    plt.close()
    print(f"✅ Saved macro plot {MACRO_PNG}")
    return True

# ----------------------------
# Fetch Google Trends (pytrends)
# ----------------------------
def fetch_trends(keywords, timeframe="today 6-m"):
    pytrends = TrendReq(hl='en-US', tz=360, requests_args=REQUESTS_ARGS)
    try:
        pytrends.build_payload(keywords, timeframe=timeframe)
        df = pytrends.interest_over_time()
        if df.empty:
            print("⚠️ No trends data returned (empty).")
            return pd.DataFrame()
        # drop isPartial column if present
        df = df.loc[:, [c for c in df.columns if c != 'isPartial']]
        return df
    except Exception as e:
        print(f"⚠️ pytrends error: {e}")
        return pd.DataFrame()

def plot_trends(df, keywords):
    if df.empty:
        print("⚠️ trends df empty — skipping trends plot")
        return False
    fig, ax = plt.subplots(figsize=(12,5))
    for kw in keywords:
        if kw in df.columns:
            ax.plot(df.index, df[kw], label=kw)
    ax.set_xlabel("Date")
    ax.set_ylabel("Interest (0-100)")
    ax.legend(loc='upper left')
    ax.grid(True)
    plt.title("Google Trends (daily) - specified keywords")
    plt.tight_layout()
    plt.savefig(TRENDS_PNG)
    plt.close()
    print(f"✅ Saved trends plot {TRENDS_PNG}")
    return True

# ----------------------------
# Main
# ----------------------------
def main():
    # create output dir if necessary
    try:
        print("Fetching macro data from FRED...")
        macro = fetch_macro()
        if not macro.empty:
            macro.to_csv(MACRO_CSV)
            print(f"✅ Saved {MACRO_CSV}")
            plot_macro(macro)
        else:
            print("⚠️ Macro data empty; no macro CSV/plot created.")

        print("Fetching Google Trends...")
        trends = fetch_trends(KEYWORDS, timeframe="today 6-m")
        if not trends.empty:
            trends.to_csv(TRENDS_CSV)
            print(f"✅ Saved {TRENDS_CSV}")
            plot_trends(trends, KEYWORDS)
        else:
            print("⚠️ Trends data empty; no trends CSV/plot created.")

        # create zip of available files (in case workflow step wants zip)
        files_to_zip = [f for f in [MACRO_PNG, MACRO_CSV, TRENDS_PNG, TRENDS_CSV] if os.path.exists(f)]
        if files_to_zip:
            zname = "market_watch_results.zip"
            with zipfile.ZipFile(zname, "w", zipfile.ZIP_DEFLATED) as z:
                for f in files_to_zip:
                    z.write(f)
            print(f"✅ Created zip {zname} with {len(files_to_zip)} files.")
        else:
            print("⚠️ No files to zip.")

    except Exception as e:
        print("🛑 Fatal error in main:", e)

if __name__ == "__main__":
    main()
