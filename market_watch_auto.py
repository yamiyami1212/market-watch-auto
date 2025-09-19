#!/usr/bin/env python3
# market_watch_auto.py
# English-only. Fetch FRED M2 (YoY%), HY spread, VIX; fetch Google Trends (5 keywords);
# produce merged monthly CSV and two PNGs: financial and trends (daily).
# Designed to run in CI (GitHub Actions).

import os
import json
import time
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from pandas_datareader.data import DataReader
from pytrends.request import TrendReq

ROOT = "."
DS_FILE = os.path.join(ROOT, "data_sources.json")  # optional, but kept for compatibility
DATE_STR = datetime.utcnow().strftime("%Y-%m-%d")

# --- CONFIG: use the 5 keywords you confirmed
KEYWORDS = [
    "sell my house fast",
    "give car back",
    "Borrow against life insurance",
    "sell my rolex watch",
    "bankruptcy lawyer"
]

# FRED series IDs (standard)
FRED_M2_SER = "M2SL"           # M2 money stock level
FRED_HY_SER = "BAMLH0A0HYM2"   # ICE BofA US High Yield OAS (bps)
FRED_VIX_SER = "VIXCLS"        # VIX index (Close)

# lookback settings
LOOKBACK_MONTHS = 6
TREND_FETCH_MONTHS = 12  # fetch 12 months then trim to last LOOKBACK_MONTHS

# outputs
OUT_MERGED_CSV = f"merged_{DATE_STR}.csv"
OUT_FIN_PNG = f"financial_{DATE_STR}.png"
OUT_TRENDS_PNG = f"trends_{DATE_STR}.png"
OUT_TRENDS_CSV = f"trends_daily_{DATE_STR}.csv"
DEBUG_DIR = "debug_outputs"
os.makedirs(DEBUG_DIR, exist_ok=True)

def fetch_fred_safe(series_id, start_date, end_date):
    try:
        df = DataReader(series_id, "fred", start_date, end_date)
        if df is None or df.empty:
            print(f"[WARN] FRED returned empty for {series_id}")
            return pd.DataFrame()
        df.columns = [series_id]
        return df
    except Exception as e:
        print(f"[ERROR] fetching FRED {series_id}: {e}")
        return pd.DataFrame()

def compute_m2_yoy_monthly(m2_df, series_id):
    if m2_df is None or m2_df.empty:
        return pd.DataFrame()
    # resample to month-end, use last observation, then compute 12-month pct change (%)
    m2_mon = m2_df.resample("M").last()
    m2_mon["M2_YoY_pct"] = m2_mon[series_id].pct_change(periods=12) * 100
    return m2_mon[["M2_YoY_pct"]]

def fetch_trends_safe(keywords, start_date, end_date, attempts=3, wait_sec=3):
    if not keywords:
        return pd.DataFrame()
    timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    pytrends = TrendReq(hl="en-US", tz=360, requests_args={
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    })
    for attempt in range(attempts):
        try:
            pytrends.build_payload(keywords, timeframe=timeframe)
            df = pytrends.interest_over_time()
            if df is None or df.empty:
                print(f"[WARN] pytrends returned empty (attempt {attempt+1})")
                time.sleep(wait_sec)
                continue
            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])
            df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            print(f"[WARN] pytrends attempt {attempt+1} failed: {e}")
            time.sleep(wait_sec)
    print("[ERROR] pytrends fetch failed after retries")
    return pd.DataFrame()

def save_placeholder(path, text="No data"):
    plt.figure(figsize=(10,6))
    plt.text(0.5, 0.5, text, ha="center", va="center", fontsize=20, alpha=0.6)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"[INFO] saved placeholder: {path}")

def main():
    # determine date ranges
    today = pd.Timestamp.today().normalize()
    start_monthly = today - pd.DateOffset(months=LOOKBACK_MONTHS + 13)  # ensure enough history for YoY
    fred_start = start_monthly
    fred_end = today
    trend_fetch_start = today - pd.DateOffset(months=TREND_FETCH_MONTHS)
    trend_fetch_end = today

    # --- FRED fetch
    print("[INFO] fetching FRED series...")
    m2_raw = fetch_fred_safe(FRED_M2_SER, fred_start, fred_end)
    hy_raw = fetch_fred_safe(FRED_HY_SER, fred_start, fred_end)
    vix_raw = fetch_fred_safe(FRED_VIX_SER, fred_start, fred_end)

    # save debug raw fred outputs
    if not m2_raw.empty:
        m2_raw.to_csv(os.path.join(DEBUG_DIR, f"m2_raw_{DATE_STR}.csv"))
    if not hy_raw.empty:
        hy_raw.to_csv(os.path.join(DEBUG_DIR, f"hy_raw_{DATE_STR}.csv"))
    if not vix_raw.empty:
        vix_raw.to_csv(os.path.join(DEBUG_DIR, f"vix_raw_{DATE_STR}.csv"))

    # compute M2 YoY monthly
    m2_yoy = compute_m2_yoy_monthly(m2_raw, FRED_M2_SER)
    if m2_yoy.empty:
        print("[WARN] M2 YoY is empty")

    # --- Google Trends fetch (fetch 12m then trim)
    print("[INFO] fetching Google Trends for keywords (5 items)...")
    trends_daily = fetch_trends_safe(KEYWORDS, trend_fetch_start, trend_fetch_end)
    if trends_daily is None or trends_daily.empty:
        print("[WARN] trends daily empty")
    else:
        trends_daily.to_csv(os.path.join(DEBUG_DIR, OUT_TRENDS_CSV))
        # trim to last LOOKBACK_MONTHS
        cutoff = today - pd.DateOffset(months=LOOKBACK_MONTHS)
        trends_daily = trends_daily[trends_daily.index >= cutoff]

    # --- convert to monthly means for alignment
    m2_mon = m2_yoy  # already monthly
    hy_mon = hy_raw.resample("M").mean() if not hy_raw.empty else pd.DataFrame()
    vix_mon = vix_raw.resample("M").mean() if not vix_raw.empty else pd.DataFrame()
    trends_mon = trends_daily.resample("M").mean() if (trends_daily is not None and not trends_daily.empty) else pd.DataFrame()

    # compute trends monthly average column
    trends_avg_mon = pd.DataFrame()
    if not trends_mon.empty:
        present = [k for k in KEYWORDS if k in trends_mon.columns]
        if present:
            trends_mon["trends_avg"] = trends_mon[present].mean(axis=1)
            trends_avg_mon = trends_mon[["trends_avg"]]

    # --- merge monthly series
    pieces = []
    names = []
    if not m2_mon.empty:
        pieces.append(m2_mon)
        names.append("M2_YoY_pct")
    if not trends_avg_mon.empty:
        pieces.append(trends_avg_mon)
        names.append("trends_avg")
    if not hy_mon.empty:
        # rename HY column to HY_Spread_bps
        if FRED_HY_SER in hy_mon.columns:
            hy_mon = hy_mon.rename(columns={FRED_HY_SER: "HY_Spread_bps"})
        pieces.append(hy_mon)
        names.append("HY_Spread_bps")
    if not vix_mon.empty:
        if FRED_VIX_SER in vix_mon.columns:
            vix_mon = vix_mon.rename(columns={FRED_VIX_SER: "VIX"})
        pieces.append(vix_mon)
        names.append("VIX")

    if not pieces:
        print("[ERROR] No monthly data available from FRED/trends. Saving placeholders and exiting.")
        save_placeholder(OUT_FIN_PNG, "No financial data")
        save_placeholder(OUT_TRENDS_PNG, "No trends data")
        return 1

    combined = pd.concat(pieces, axis=1)
    combined = combined.sort_index().ffill().bfill()
    combined.to_csv(OUT_MERGED_CSV)
    print(f"[INFO] saved merged CSV: {OUT_MERGED_CSV}")

    # --- plot financial: left = M2 YoY & trends_avg (if present), right = HY & VIX
    fig, axL = plt.subplots(figsize=(12,6))
    plotted_left = False
    if "M2_YoY_pct" in combined.columns:
        axL.plot(combined.index, combined["M2_YoY_pct"], label="M2 YoY (%)", color="tab:blue", linewidth=2)
        plotted_left = True
    if "trends_avg" in combined.columns:
        axL.plot(combined.index, combined["trends_avg"], label="Trends Avg (monthly)", color="tab:cyan", linestyle="--")
        plotted_left = True

    axL.set_xlabel("Date")
    axL.set_ylabel("Left axis: M2 YoY (%) / Trends Avg")

    axR = axL.twinx()
    plotted_right = False
    if "HY_Spread_bps" in combined.columns:
        axR.plot(combined.index, combined["HY_Spread_bps"], label="HY Spread (bps)", color="tab:red", linewidth=1.5)
        plotted_right = True
    if "VIX" in combined.columns:
        axR.plot(combined.index, combined["VIX"], label="VIX", color="tab:orange", linestyle=":")
        plotted_right = True

    # combined legend
    linesL, labelsL = axL.get_legend_handles_labels()
    linesR, labelsR = axR.get_legend_handles_labels()
    axL.legend(linesL + linesR, labelsL + labelsR, loc="best")
    axL.grid(True)
    plt.title("M2 YoY, Trends Avg, HY Spread, VIX")
    plt.tight_layout()
    plt.savefig(OUT_FIN_PNG)
    plt.close()
    print(f"[INFO] saved financial PNG: {OUT_FIN_PNG}")

    # --- save trends daily CSV and plot separately
    if trends_daily is None or trends_daily.empty:
        save_placeholder(OUT_TRENDS_PNG, "No trends data")
    else:
        trends_daily.to_csv(OUT_TRENDS_CSV)
        plt.figure(figsize=(12,6))
        for kw in KEYWORDS:
            if kw in trends_daily.columns:
                plt.plot(trends_daily.index, trends_daily[kw], label=kw)
            else:
                print(f"[WARN] trends missing column: {kw}")
        plt.legend()
        plt.title("Google Trends (daily) - specified keywords")
        plt.xlabel("Date")
        plt.ylabel("Interest (0-100)")
        plt.xticks(rotation=30)
        plt.tight_layout()
        plt.savefig(OUT_TRENDS_PNG)
        plt.close()
        print(f"[INFO] saved trends PNG: {OUT_TRENDS_PNG}")

    print("[INFO] done.")
    return 0

if __name__ == "__main__":
    exit(main())
