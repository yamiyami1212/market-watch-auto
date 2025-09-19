#!/usr/bin/env python3
# market_watch_macro.py
# Fetch M2 (YoY%), HY spread, VIX from FRED and output CSV + PNG reliably.

import os
import time
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from pandas_datareader import data as pdr

# CONFIG
FRED_M2 = "M2SL"
FRED_HY = "BAMLH0A0HYM2"
FRED_VIX = "VIXCLS"

# Output files (fixed names used by workflow)
OUT_CSV = "macro_data.csv"
OUT_PNG = "macro_graph.png"
RAW_DIR = "debug_raw"
os.makedirs(RAW_DIR, exist_ok=True)

# Date range: go back enough to compute YoY (use 24 months as safe)
END = pd.Timestamp.today().normalize()
START = END - pd.DateOffset(months=24)

def fetch_fred(series_id, start=START, end=END, tries=3, pause=3):
    last_err = None
    for i in range(tries):
        try:
            print(f"[FRED] fetching {series_id} (attempt {i+1})...", flush=True)
            df = pdr.DataReader(series_id, "fred", start, end)
            if df is None or df.empty:
                print(f"[FRED] Warning: returned empty for {series_id}", flush=True)
                return pd.DataFrame()
            df.columns = [series_id]
            # save raw
            raw_path = os.path.join(RAW_DIR, f"{series_id}_raw.csv")
            df.to_csv(raw_path)
            print(f"[FRED] saved raw to {raw_path}", flush=True)
            return df
        except Exception as e:
            last_err = e
            print(f"[FRED] attempt {i+1} failed for {series_id}: {e}", flush=True)
            time.sleep(pause)
    raise RuntimeError(f"Failed to fetch {series_id} after {tries} attempts. Last error: {last_err}")

def compute_m2_yoy(m2_df, series_id=FRED_M2):
    if m2_df is None or m2_df.empty:
        return pd.DataFrame()
    # resample to month-end using last observation
    m2_mon = m2_df.resample("M").last()
    m2_mon = m2_mon.sort_index()
    # compute 12-month pct change
    m2_mon["M2_YoY_pct"] = m2_mon[series_id].pct_change(periods=12) * 100.0
    return m2_mon[["M2_YoY_pct"]]

def hy_to_bps(hy_df, series_id=FRED_HY):
    if hy_df is None or hy_df.empty:
        return pd.DataFrame()
    hy_mon = hy_df.resample("M").last()
    hy_mon = hy_mon.sort_index()
    # check scale: if median < 20 treat as percent (e.g., 3.1 -> 310 bps)
    med = hy_mon[series_id].median()
    if pd.notna(med) and abs(med) < 20:
        hy_mon["HY_spread_bps"] = hy_mon[series_id] * 100.0
        print(f"[HY] median {med:.3f} <20 -> converted to bps by *100", flush=True)
    else:
        hy_mon["HY_spread_bps"] = hy_mon[series_id]
        print(f"[HY] median {med:.3f} -> assumed already in bps or large units", flush=True)
    return hy_mon[["HY_spread_bps"]]

def vix_monthly(vix_df, series_id=FRED_VIX):
    if vix_df is None or vix_df.empty:
        return pd.DataFrame()
    vix_mon = vix_df.resample("M").last()
    vix_mon = vix_mon.sort_index()
    vix_mon.columns = ["VIX"]
    return vix_mon[["VIX"]]

def main():
    print("Start macro fetch", flush=True)
    m2_raw = fetch_fred(FRED_M2)
    hy_raw = fetch_fred(FRED_HY)
    vix_raw = fetch_fred(FRED_VIX)

    m2_yoy = compute_m2_yoy(m2_raw, FRED_M2)
    hy_bps = hy_to_bps(hy_raw, FRED_HY)
    vix_mon = vix_monthly(vix_raw, FRED_VIX)

    # Combine on month-end index
    dfs = [d for d in [m2_yoy, hy_bps, vix_mon] if not d.empty]
    if not dfs:
        print("No data available from FRED. Exiting.", flush=True)
        # create placeholder CSV
        pd.DataFrame().to_csv(OUT_CSV)
        return 1

    combined = pd.concat(dfs, axis=1)
    combined = combined.sort_index().ffill().bfill()
    # Force DATE column as ISO string of index (month end)
    out = combined.copy()
    out.insert(0, "DATE", out.index.strftime("%Y-%m-%d"))
    out.to_csv(OUT_CSV, index=False, float_format="%.6f")
    print(f"Saved {OUT_CSV}", flush=True)

    # Plot: left = M2 YoY and HY_spread_bps; right = VIX
    fig, axL = plt.subplots(figsize=(12,6))
    if "M2_YoY_pct" in combined.columns:
        axL.plot(combined.index, combined["M2_YoY_pct"], label="M2 YoY (%)", color="tab:blue", linewidth=2)
    if "HY_spread_bps" in combined.columns:
        axL.plot(combined.index, combined["HY_spread_bps"], label="HY Spread (bps)", color="tab:red", linewidth=1.5)
    axL.set_xlabel("Date")
    axL.set_ylabel("Left axis: M2 YoY (%) / HY Spread (bps)")
    axL.grid(True, linestyle="--", alpha=0.4)

    axR = axL.twinx()
    if "VIX" in combined.columns:
        axR.plot(combined.index, combined["VIX"], label="VIX", color="tab:orange", linestyle="--")
        axR.set_ylabel("VIX")

    # legend
    linesL, labelsL = axL.get_legend_handles_labels()
    linesR, labelsR = axR.get_legend_handles_labels()
    axL.legend(linesL + linesR, labelsL + labelsR, loc="upper left")

    plt.title("M2 YoY (%) & HY Spread (bps) / VIX")
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    plt.close()
    print(f"Saved {OUT_PNG}", flush=True)
    return 0

if __name__ == "__main__":
    exit(main())
