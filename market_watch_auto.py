#!/usr/bin/env python3
# market_watch_auto.py
# English-only. Reads data_sources.json and creates financial + trends outputs.

import os
import json
import time
from datetime import datetime, timedelta

import pandas as pd
import matplotlib.pyplot as plt
from pandas_datareader.data import DataReader
from pytrends.request import TrendReq

# config
ROOT = "."
DS_FILE = os.path.join(ROOT, "data_sources.json")
LOOKBACK_MONTHS = 6
TREND_LOOKBACK_MONTHS = 12  # fetch 12m then trim to 6m for stability
DATE_STR = datetime.utcnow().strftime("%Y-%m-%d")

# outputs
FIN_PNG = f"financial_{DATE_STR}.png"
TRENDS_PNG = f"trends_{DATE_STR}.png"
MERGED_CSV = f"merged_{DATE_STR}.csv"
TRENDS_CSV = f"trends_{DATE_STR}.csv"

# load data sources
with open(DS_FILE, "r", encoding="utf-8") as f:
    ds = json.load(f)

M2_SERIES = ds.get("m2", "M2SL")
VIX_SERIES = ds.get("vix", "VIXCLS")
HY_SERIES = ds.get("hy_spread", "BAMLH0A0HYM2")
KEYWORDS = ds.get("google_trends_keywords", [])

# date range
end = pd.Timestamp.today().normalize()
start = end - pd.DateOffset(months=LOOKBACK_MONTHS)
trend_start = end - pd.DateOffset(months=TREND_LOOKBACK_MONTHS)
trend_timeframe = f"{trend_start.strftime('%Y-%m-%d')} {end.strftime('%Y-%m-%d')}"

def fetch_fred(series_id, start_date, end_date):
    try:
        df = DataReader(series_id, "fred", start_date, end_date)
        df.columns = [series_id]
        return df
    except Exception as e:
        print(f"Error fetching {series_id} from FRED: {e}")
        return pd.DataFrame()

def safe_compute_m2_yoy(m2_df):
    if m2_df.empty:
        return pd.DataFrame()
    # ensure daily freq then compute 12-month pct change
    m2_daily = m2_df.asfreq('D').ffill()
    # use 365 days approx for YoY on daily series
    m2_daily["M2_YoY_pct"] = m2_daily.iloc[:, 0].pct_change(periods=365) * 100
    return m2_daily[["M2_YoY_pct"]]

def fetch_trends(keywords, timeframe, attempts=3, sleep_sec=5):
    if not keywords:
        return pd.DataFrame()
    pytrends = TrendReq(hl="en-US", tz=360, requests_args={
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    })
    for attempt in range(attempts):
        try:
            pytrends.build_payload(keywords, timeframe=timeframe)
            df = pytrends.interest_over_time()
            if df is None or df.empty:
                print(f"Attempt {attempt+1}: empty trends result")
                time.sleep(sleep_sec)
                continue
            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])
            # ensure datetime index and rename to daily date index
            df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            print(f"Attempt {attempt+1} failed for pytrends: {e}")
            time.sleep(sleep_sec)
    print("pytrends fetch failed after retries")
    return pd.DataFrame()

def to_monthly(df, how="mean"):
    if df is None or df.empty:
        return pd.DataFrame()
    # convert to monthly end frequency
    if isinstance(df.index, pd.DatetimeIndex):
        if how == "mean":
            return df.resample("M").mean()
        else:
            return df.resample("M").last()
    return pd.DataFrame()

def save_placeholder_png(path, text="No data"):
    plt.figure(figsize=(10,6))
    plt.text(0.5, 0.5, text, ha="center", va="center", fontsize=24, alpha=0.6)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Saved placeholder: {path}")

def main():
    # 1) Fetch FRED series
    m2 = fetch_fred(M2_SERIES, start - pd.DateOffset(days=10), end)
    hy = fetch_fred(HY_SERIES, start - pd.DateOffset(days=10), end)
    vix = fetch_fred(VIX_SERIES, start - pd.DateOffset(days=10), end)

    # 2) Compute M2 YoY
    m2_yoy = safe_compute_m2_yoy(m2)

    # 3) Fetch trends (12m then trim to last 6m)
    trends_df = fetch_trends(KEYWORDS, timeframe=trend_timeframe)
    if trends_df.empty:
        print("Warning: trends empty")
    else:
        # trim to last LOOKBACK_MONTHS
        cutoff = end - pd.DateOffset(months=LOOKBACK_MONTHS)
        trends_df = trends_df[trends_df.index >= cutoff]

    # 4) Convert all to monthly
    m2_mon = to_monthly(m2_yoy, how="mean")
    hy_mon = to_monthly(hy, how="mean")
    vix_mon = to_monthly(vix, how="mean")
    trends_mon = to_monthly(trends_df, how="mean")

    # 5) compute trends average separately (if available)
    if not trends_mon.empty:
        trends_mon["trends_avg"] = trends_mon[KEYWORDS].mean(axis=1) if all(k in trends_mon.columns for k in KEYWORDS) else trends_mon.mean(axis=1)
        trends_avg = trends_mon[["trends_avg"]]
    else:
        trends_avg = pd.DataFrame()

    # 6) Merge financial series: M2 YoY (left), HY & VIX (right)
    dfs = []
    if not m2_mon.empty:
        dfs.append(m2_mon)
    if not trends_avg.empty:
        dfs.append(trends_avg)  # NOTE: trends_avg will be plotted separately per request, but include for combined left axis only if desired
    if not hy_mon.empty:
        dfs.append(hy_mon.rename(columns={HY_SERIES: "HY_Spread_bps"}))
    if not vix_mon.empty:
        dfs.append(vix_mon.rename(columns={VIX_SERIES: "VIX"}))

    if not dfs:
        print("No data from any source. Creating placeholders.")
        save_placeholder_png(FIN_PNG, text="No financial data")
        save_placeholder_png(TRENDS_PNG, text="No trends data")
        return 0

    combined = pd.concat(dfs, axis=1)
    combined = combined.sort_index().ffill().bfill()
    combined.to_csv(MERGED_CSV)
    print("Saved merged CSV:", MERGED_CSV)

    # 7) Plot financial combined: left = M2 YoY (and optional trends_avg), right = HY & VIX
    fig, axL = plt.subplots(figsize=(12,6))
    left_plotted = False
    if "M2_YoY_pct" in combined.columns:
        axL.plot(combined.index, combined["M2_YoY_pct"], label="M2 YoY (%)", color="tab:blue", linewidth=2)
        left_plotted = True
    if "trends_avg" in combined.columns:
        axL.plot(combined.index, combined["trends_avg"], label="Trends Avg (monthly)", color="tab:cyan", linestyle="--")
        left_plotted = True

    axL.set_xlabel("Date")
    axL.set_ylabel("Left axis: M2 YoY (%) / Trends Avg")
    axL.tick_params(axis="y")

    axR = axL.twinx()
    right_plotted = False
    if "HY_Spread_bps" in combined.columns:
        axR.plot(combined.index, combined["HY_Spread_bps"], label="HY Spread (bps)", color="tab:red", linewidth=1.5)
        right_plotted = True
    if "VIX" in combined.columns:
        axR.plot(combined.index, combined["VIX"], label="VIX", color="tab:orange", linestyle=":")
        right_plotted = True

    if left_plotted or right_plotted:
        linesL, labelsL = axL.get_legend_handles_labels()
        linesR, labelsR = axR.get_legend_handles_labels()
        axL.legend(linesL + linesR, labelsL + labelsR, loc="best")
    axL.grid(True)
    plt.title("M2 YoY, Trends Avg (opt), HY Spread, VIX")
    plt.tight_layout()
    plt.savefig(FIN_PNG)
    plt.close()
    print("Saved financial plot:", FIN_PNG)

    # 8) Save trends CSV and plot separately (each of 6 in one plot)
    if trends_df is None or trends_df.empty:
        save_placeholder_png(TRENDS_PNG, text="No trends data")
    else:
        # save raw daily trends for inspection
        trends_df.to_csv(TRENDS_CSV)
        print("Saved trends CSV:", TRENDS_CSV)
        plt.figure(figsize=(12,6))
        for kw in KEYWORDS:
            if kw in trends_df.columns:
                plt.plot(trends_df.index, trends_df[kw], label=kw)
            else:
                print(f"Keyword missing in trends_df: {kw}")
        plt.legend()
        plt.title("Google Trends (daily) - specified keywords")
        plt.xlabel("Date")
        plt.ylabel("Interest (0-100)")
        plt.xticks(rotation=30)
        plt.tight_layout()
        plt.savefig(TRENDS_PNG)
        plt.close()
        print("Saved trends plot:", TRENDS_PNG)

    return 0

if __name__ == "__main__":
    exit(main())
