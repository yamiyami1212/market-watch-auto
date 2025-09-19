# market_watch_auto.py
# PURPOSE: fetch M2 YoY (FRED), HY spread (FRED), VIX (FRED), Google Trends for keywords,
#          combine and produce a plot trend.png
# USAGE: python market_watch_auto.py

import os
import io
import zipfile
from datetime import datetime
import time

import pandas as pd
import matplotlib.pyplot as plt
from pandas_datareader.data import DataReader
from pytrends.request import TrendReq

# --- CONFIG
KEYWORDS = ["Bitcoin", "Apple", "Google", "Amazon"]  # Google Trends keywords
FRED_M2_SERIES = "M2SL"            # M2 money stock level
FRED_HY_SPREAD = "BAMLH0A0HYM2"    # ICE BofA US High Yield OAS (bps)
FRED_VIX = "VIXCLS"                # CBOE VIX index (Close)
LOOKBACK_MONTHS = 6

# calculate date range
end = pd.Timestamp.today().normalize()
start = end - pd.DateOffset(months=LOOKBACK_MONTHS)

# --- Fetch FRED time series function
def fetch_fred_series(series_id, start_date, end_date):
    df = DataReader(series_id, "fred", start_date, end_date)
    df.columns = [series_id]
    return df

# --- Fetch Google Trends
def fetch_google_trends(keywords, timeframe="today 6-m", hl="en-US", tz=360, attempts=3):
    pytrends = TrendReq(hl=hl, tz=tz)
    for attempt in range(attempts):
        try:
            pytrends.build_payload(keywords, timeframe=timeframe)
            data = pytrends.interest_over_time()
            if data.empty:
                return pd.DataFrame()
            # remove isPartial if exists
            if "isPartial" in data.columns:
                data = data.drop(columns=["isPartial"])
            # average across keywords (row-wise mean)
            data["trends_avg"] = data[keywords].mean(axis=1)
            return data[["trends_avg"]]
        except Exception as e:
            print(f"Attempt {attempt+1} failed for Google Trends: {e}")
            time.sleep(3)
    print("Google Trends fetch failed after retries.")
    return pd.DataFrame()

# --- Main
def main():
    # 1) Fetch FRED series
    try:
        m2 = fetch_fred_series(FRED_M2_SERIES, start, end)
        hy = fetch_fred_series(FRED_HY_SPREAD, start, end)
        vix = fetch_fred_series(FRED_VIX, start, end)
    except Exception as e:
        print("Error fetching from FRED:", e)
        return 1

    # 2) Compute M2 YoY growth rate (%) from level
    m2_yoy = (m2.pct_change(periods=12) * 100).rename(columns={FRED_M2_SERIES: "M2_YoY_pct"})
    # drop NaNs
    m2_yoy = m2_yoy.dropna()

    # 3) Fetch Google Trends
    trends = fetch_google_trends(KEYWORDS, timeframe=f"{LOOKBACK_MONTHS}m")
    # if empty, continue but warn
    if trends.empty:
        print("Warning: Google Trends data empty. Plot will omit trends_avg.")

    # 4) Align/resample to monthly to match M2 (M2 is monthly)
    # Convert all to monthly end (or monthly mean)
    def to_monthly_mean(df):
        if df is None or df.empty:
            return pd.DataFrame()
        return df.resample("M").mean()

    m2_month = to_monthly_mean(m2_yoy)
    hy_month = to_monthly_mean(hy)
    vix_month = to_monthly_mean(vix)
    trends_month = to_monthly_mean(trends)

    # 5) Combine into single DataFrame
    pieces = [m2_month, trends_month, hy_month, vix_month]
    combined = pd.concat(pieces, axis=1)
    combined = combined.dropna(how="all")  # keep rows where at least one exists

    # rename columns for clarity
    rename_map = {
        FRED_HY_SPREAD: "HY_Spread_bps",
        FRED_VIX: "VIX"
    }
    combined = combined.rename(columns=rename_map)

    # 6) If any column missing, fill with NaN (already)
    print("Combined columns:", combined.columns.tolist())

    # 7) Plot
    plt.figure(figsize=(12, 6))
    ax = plt.gca()

    # left axis: M2 YoY and Trends average (if present)
    if "M2_YoY_pct" in combined.columns:
        ax.plot(combined.index, combined["M2_YoY_pct"], label="M2 YoY (%)", color="tab:blue", linewidth=2)
    if "trends_avg" in combined.columns:
        ax.plot(combined.index, combined["trends_avg"], label="Google Trends Avg", color="tab:cyan", linestyle="--")

    ax.set_xlabel("Date")
    ax.set_ylabel("M2 YoY (%) / Trends Avg")
    ax.tick_params(axis="y")

    # right axis: HY spread and VIX
    ax2 = ax.twinx()
    if "HY_Spread_bps" in combined.columns:
        ax2.plot(combined.index, combined["HY_Spread_bps"], label="HY Spread (bps)", color="tab:red", linewidth=1.5)
    if "VIX" in combined.columns:
        ax2.plot(combined.index, combined["VIX"], label="VIX", color="tab:orange", linestyle=":")

    ax2.set_ylabel("HY Spread (bps) / VIX")
    ax2.tick_params(axis="y")

    # legend: combine legends from both axes
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="best")

    plt.title("Google Trends & Macro / Market Indicators")
    plt.grid(True)
    plt.tight_layout()

    out_png = "trend.png"
    plt.savefig(out_png)
    print(f"Saved plot to {out_png}")

    # 8) Create a zip artifact (so Actions can upload)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    zip_name = f"trend-{date_str}.zip"
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out_png)
    print(f"Saved artifact zip: {zip_name}")

    return 0

if __name__ == "__main__":
    exit(main())
