#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch M2 (YoY %), HY spread (bps), and VIX from FRED and plot:
 - Left axis: M2 YoY (%) and HY spread (bps)
 - Right axis: VIX
Saves macro_trends.png and macro_data.csv
"""
import json
import sys
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from pandas_datareader import data as pdr

# Load config
def load_config():
    try:
        with open("data_sources.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        # fallback defaults
        cfg = {
            "fred_series": {"m2": "M2SL", "hy_spread": "BAMLH0A0HYM2", "vix": "VIXCLS"},
            "months_back": 18
        }
    return cfg

cfg = load_config()
SERIES_M2 = cfg["fred_series"].get("m2", "M2SL")
SERIES_HY = cfg["fred_series"].get("hy_spread", "BAMLH0A0HYM2")
SERIES_VIX = cfg["fred_series"].get("vix", "VIXCLS")
months_back = int(cfg.get("months_back", 18))

END = datetime.date.today()
START = (pd.Timestamp(END) - pd.DateOffset(months=months_back)).date()

OUT_PLOT = "macro_trends.png"
OUT_CSV = "macro_data.csv"

def fetch_series(symbol, source="fred", start=START, end=END, tries=3, pause=3):
    last_exc = None
    for attempt in range(1, tries+1):
        try:
            print(f"[FRED] Fetching {symbol} try {attempt} ...", flush=True)
            s = pdr.DataReader(symbol, source, start, end)
            if isinstance(s, pd.Series):
                s = s.to_frame(name=symbol)
            else:
                s.columns = [symbol]
            return s
        except Exception as e:
            print(f"[FRED] Warning: {symbol} fetch failed (attempt {attempt}): {e}", flush=True)
            last_exc = e
            time.sleep(pause)
    raise RuntimeError(f"Failed to fetch {symbol} after {tries} attempts: {last_exc}")

def main():
    print(f"Fetching from FRED: {START} -> {END}", flush=True)

    m2 = fetch_series(SERIES_M2)
    hy = fetch_series(SERIES_HY)
    vix = fetch_series(SERIES_VIX)

    m2.columns = ["M2"]
    hy.columns = ["HY_raw"]
    vix.columns = ["VIX"]

    # monthly alignment (end of month)
    m2_m = m2.resample("M").last()
    hy_m = hy.resample("M").last()
    vix_m = vix.resample("M").last()

    # M2 YoY %
    m2_yoy = m2_m.pct_change(12) * 100
    m2_yoy.columns = ["M2_YoY_pct"]

    # HY spread: convert to bps if needed
    med = hy_m["HY_raw"].median()
    if pd.notna(med) and abs(med) < 10:
        # likely percent -> convert to bps
        hy_m["HY_spread_bps"] = hy_m["HY_raw"] * 100.0
    else:
        hy_m["HY_spread_bps"] = hy_m["HY_raw"]

    hy_final = hy_m[["HY_spread_bps"]]

    # Combine
    df = pd.concat([m2_yoy, hy_final, vix_m], axis=1)
    df = df.sort_index()
    df = df.dropna(how="all")

    if df.empty:
        print("No data available after fetch. Exiting.", flush=True)
        sys.exit(0)

    df.to_csv(OUT_CSV, float_format="%.6f")
    print(f"Wrote {OUT_CSV}", flush=True)

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    if "M2_YoY_pct" in df.columns:
        ax.plot(df.index, df["M2_YoY_pct"], label="M2 YoY (%)", color="tab:blue", linewidth=2)
    if "HY_spread_bps" in df.columns:
        ax.plot(df.index, df["HY_spread_bps"], label="HY Spread (bps)", color="tab:red", linewidth=1.5)

    ax.set_xlabel("Date")
    ax.set_ylabel("Left axis: M2 YoY (%) / HY Spread (bps)")
    ax.grid(True, linestyle="--", alpha=0.4)

    ax2 = ax.twinx()
    if "VIX" in df.columns:
        ax2.plot(df.index, df["VIX"], label="VIX", color="tab:orange", linewidth=1.5, linestyle="--")
    ax2.set_ylabel("VIX")

    # combined legend
    lines, labels = ax.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax.legend(lines + l2, labels + lab2, loc="upper left")

    plt.title("M2 YoY, HY Spread (bps) and VIX (monthly)")
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(OUT_PLOT, dpi=150)
    print(f"Wrote {OUT_PLOT}", flush=True)
    plt.close(fig)

if __name__ == "__main__":
    main()
