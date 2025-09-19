#!/usr/bin/env python3
# market_watch_auto.py
# Fetch FRED macro series and Google Trends for specified keywords (handles 6 keywords by batching).
# Saves diagnostics and outputs (PNGs, CSVs).

import os
import json
import time
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from pandas_datareader.data import DataReader
from pytrends.request import TrendReq

ROOT = "."
DS_FILE = os.path.join(ROOT, "data_sources.json")
DATE_STR = datetime.utcnow().strftime("%Y-%m-%d")
LOOKBACK_MONTHS = 6
TREND_LOOKBACK_MONTHS = 12  # fetch 12m then trim to last 6m

# outputs
OUT_FIN = f"financial_{DATE_STR}.png"
OUT_TRENDS = f"trends_{DATE_STR}.png"
OUT_MERGED = f"merged_{DATE_STR}.csv"
OUT_TRENDS_RAW = f"trends_raw_{DATE_STR}.csv"
OUT_DEBUG_DIR = "debug_outputs"
os.makedirs(OUT_DEBUG_DIR, exist_ok=True)

def load_sources():
    with open(DS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_fred(series_id, start, end):
    try:
        df = DataReader(series_id, "fred", start, end)
        if df is None or df.empty:
            print(f"[WARN] FRED returned empty for {series_id}")
            return pd.DataFrame()
        df.columns = [series_id]
        return df
    except Exception as e:
        print(f"[ERROR] fetching FRED {series_id}: {e}")
        return pd.DataFrame()

def compute_m2_yoy(m2_df, series_id):
    if m2_df.empty:
        return pd.DataFrame()
    # convert to monthly last and compute 12-month pct change
    m2_mon = m2_df.resample("M").last()
    m2_mon["M2_YoY_pct"] = m2_mon[series_id].pct_change(periods=12) * 100
    return m2_mon[["M2_YoY_pct"]]

def pytrends_fetch_with_anchor(keywords, timeframe, anchor_keyword=None, attempts=3):
    """
    Fetch trends for a list of keywords.
    If keywords > 5, use two batches: batch1 = first 5, batch2 = [anchor + remaining]
    Anchor must be present in both batches to align scales.
    Returns combined daily DataFrame (index datetime, columns keywords).
    """
    if not keywords:
        return pd.DataFrame()

    pytrends = TrendReq(hl="en-US", tz=360, requests_args={
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    })

    # helper
    def try_build_and_get(klist):
        for att in range(attempts):
            try:
                pytrends.build_payload(klist, timeframe=timeframe)
                df = pytrends.interest_over_time()
                if df is None:
                    print(f"[WARN] pytrends returned None for {klist}")
                    time.sleep(2)
                    continue
                if "isPartial" in df.columns:
                    df = df.drop(columns=["isPartial"])
                df.index = pd.to_datetime(df.index)
                return df
            except Exception as e:
                print(f"[WARN] pytrends attempt {att+1} failed for {klist}: {e}")
                time.sleep(2)
        return pd.DataFrame()

    # if <=5 just fetch once
    if len(keywords) <= 5:
        df = try_build_and_get(keywords)
        return df

    # len > 5: use anchor approach
    # choose anchor as first keyword if not provided
    if not anchor_keyword:
        anchor_keyword = keywords[0]

    # batch1: first 5
    batch1 = keywords[:5]
    # batch2: anchor + remaining (ensure not duplicate)
    remaining = [k for k in keywords if k not in batch1]
    batch2 = [anchor_keyword] + remaining

    df1 = try_build_and_get(batch1)
    df2 = try_build_and_get(batch2)

    # save raw batch outputs for debugging
    if not df1.empty:
        df1.to_csv(os.path.join(OUT_DEBUG_DIR, f"pytrends_batch1_{DATE_STR}.csv"))
    if not df2.empty:
        df2.to_csv(os.path.join(OUT_DEBUG_DIR, f"pytrends_batch2_{DATE_STR}.csv"))

    if df1.empty and df2.empty:
        return pd.DataFrame()
    if df2.empty:
        return df1
    if df1.empty:
        # drop anchor col from df2 if anchor present but no baseline
        return df2

    # Align df2 to df1 using anchor scaling
    if anchor_keyword not in df1.columns or anchor_keyword not in df2.columns:
        # cannot align; concatenate with NaNs
        combined = pd.concat([df1, df2.drop(columns=[anchor_keyword], errors="ignore")], axis=1)
        return combined

    # compute scale factor using overlapping period means (use mean of overlapping index)
    common_index = df1.index.intersection(df2.index)
    if common_index.empty:
        # no overlap -> scale by ratio of max values (fallback)
        a1 = df1[anchor_keyword].max() if not df1[anchor_keyword].empty else 1.0
        a2 = df2[anchor_keyword].max() if not df2[anchor_keyword].empty else 1.0
        scale = (a1 / a2) if a2 != 0 else 1.0
    else:
        a1 = df1.loc[common_index, anchor_keyword].mean()
        a2 = df2.loc[common_index, anchor_keyword].mean()
        scale = (a1 / a2) if a2 != 0 else 1.0

    # apply scale to df2 (all columns except anchor) so values align with df1 scale
    df2_scaled = df2.copy()
    for col in df2.columns:
        if col == anchor_keyword:
            continue
        df2_scaled[col] = df2_scaled[col] * scale

    # merge datasets: prefer df1 values where available, then df2_scaled where missing
    combined = pd.concat([df1, df2_scaled.drop(columns=[anchor_keyword], errors="ignore")], axis=1)
    # sort columns in original keyword order
    cols_order = []
    for k in keywords:
        if k in combined.columns:
            cols_order.append(k)
    combined = combined[cols_order]
    return combined

def to_monthly_mean(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.resample("M").mean()

def save_placeholder(path, text="No data"):
    plt.figure(figsize=(10,6))
    plt.text(0.5, 0.5, text, ha="center", va="center", fontsize=20, alpha=0.6)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"[INFO] placeholder saved: {path}")

def main():
    # load dataset config
    ds = load_sources()
    M2_SER = ds.get("m2", "M2SL")
    VIX_SER = ds.get("vix", "VIXCLS")
    HY_SER = ds.get("hy_spread", "BAMLH0A0HYM2")
    KEYWORDS = ds.get("google_trends_keywords", [])

    today = pd.Timestamp.today().normalize()
    start = today - pd.DateOffset(months=LOOKBACK_MONTHS)
    trend_start = today - pd.DateOffset(months=TREND_LOOKBACK_MONTHS)
    trend_timeframe = f"{trend_start.strftime('%Y-%m-%d')} {today.strftime('%Y-%m-%d')}"

    print("[INFO] Fetching FRED series...")
    m2_raw = fetch_fred(M2_SER, start - pd.DateOffset(days=10), today)
    hy_raw = fetch_fred(HY_SER, start - pd.DateOffset(days=10), today)
    vix_raw = fetch_fred(VIX_SER, start - pd.DateOffset(days=10), today)

    # save raw fred for debugging
    if not m2_raw.empty:
        m2_raw.to_csv(os.path.join(OUT_DEBUG_DIR, f"m2_raw_{DATE_STR}.csv"))
    if not hy_raw.empty:
        hy_raw.to_csv(os.path.join(OUT_DEBUG_DIR, f"hy_raw_{DATE_STR}.csv"))
    if not vix_raw.empty:
        vix_raw.to_csv(os.path.join(OUT_DEBUG_DIR, f"vix_raw_{DATE_STR}.csv"))

    # compute M2 YoY monthly
    m2_yoy = compute_m2_yoy(m2_raw, M2_SER)
    if m2_yoy.empty:
        print("[WARN] M2 YoY empty")

    # fetch trends with anchor method if needed
    print("[INFO] Fetching Google Trends (may batch to respect pytrends limit)...")
    trends_daily = pytrends_fetch_with_anchor(KEYWORDS, timeframe=trend_timeframe, anchor_keyword=(KEYWORDS[0] if KEYWORDS else None))
    if trends_daily is None or trends_daily.empty:
        print("[WARN] No trends data returned")
    else:
        trends_daily.to_csv(os.path.join(OUT_DEBUG_DIR, OUT_TRENDS_RAW))

    # convert to monthly
    m2_mon = m2_yoy  # already monthly
    hy_mon = hy_raw.resample("M").mean() if not hy_raw.empty else pd.DataFrame()
    vix_mon = vix_raw.resample("M").mean() if not vix_raw.empty else pd.DataFrame()
    trends_mon = trends_daily.resample("M").mean() if (trends_daily is not None and not trends_daily.empty) else pd.DataFrame()

    # compute trends average monthly if we have keyword columns
    trends_avg = pd.DataFrame()
    if not trends_mon.empty:
        present = [k for k in KEYWORDS if k in trends_mon.columns]
        if present:
            trends_mon["trends_avg"] = trends_mon[present].mean(axis=1)
            trends_avg = trends_mon[["trends_avg"]]

    # merge everything
    pieces = {}
    if not m2_mon.empty:
        pieces["M2_YoY_pct"] = m2_mon["M2_YoY_pct"]
    if not trends_avg.empty:
        pieces["trends_avg"] = trends_avg["trends_avg"]
    if not hy_mon.empty:
        pieces["HY_Spread_bps"] = hy_mon[HY_SER] if HY_SER in hy_mon.columns else hy_mon.iloc[:,0]
    if not vix_mon.empty:
        pieces["VIX"] = vix_mon[VIX_SER] if VIX_SER in vix_mon.columns else vix_mon.iloc[:,0]

    if not pieces:
        print("[ERROR] No data to plot. Saving placeholders.")
        save_placeholder(OUT_FIN, "No financial data")
        save_placeholder(OUT_TRENDS, "No trends data")
        return 1

    combined = pd.concat(pieces.values(), axis=1, keys=pieces.keys())
    combined = combined.sort_index().ffill().bfill()
    combined.to_csv(OUT_MERGED)
    print(f"[INFO] saved merged CSV: {OUT_MERGED}")

    # financial plot: left axis = M2 YoY & trends_avg(opt), right axis = HY & VIX
    fig, axL = plt.subplots(figsize=(12,6))
    left_items = []
    if "M2_YoY_pct" in combined.columns:
        axL.plot(combined.index, combined["M2_YoY_pct"], label="M2 YoY (%)", linewidth=2)
        left_items.append("M2_YoY_pct")
    if "trends_avg" in combined.columns:
        axL.plot(combined.index, combined["trends_avg"], label="Trends Avg (monthly)", linestyle="--")
        left_items.append("trends_avg")
    axL.set_xlabel("Date")
    axL.set_ylabel("Left axis: M2 YoY (%) / Trends Avg")

    axR = axL.twinx()
    right_items = []
    if "HY_Spread_bps" in combined.columns:
        axR.plot(combined.index, combined["HY_Spread_bps"], label="HY Spread (bps)", color="tab:red")
        right_items.append("HY_Spread_bps")
    if "VIX" in combined.columns:
        axR.plot(combined.index, combined["VIX"], label="VIX", color="tab:orange", linestyle=":")
        right_items.append("VIX")

    # legend combining
    linesL, labelsL = axL.get_legend_handles_labels()
    linesR, labelsR = axR.get_legend_handles_labels()
    axL.legend(linesL + linesR, labelsL + labelsR, loc="best")
    axL.grid(True)
    plt.title("M2 YoY, Trends Avg (opt), HY Spread, VIX")
    plt.tight_layout()
    plt.savefig(OUT_FIN)
    plt.close()
    print(f"[INFO] saved financial plot: {OUT_FIN}")

    # trends plot: daily series for keywords
    if trends_daily is None or trends_daily.empty:
        save_placeholder(OUT_TRENDS, "No trends data")
    else:
        trends_daily.to_csv(f"trends_daily_{DATE_STR}.csv")
        plt.figure(figsize=(12,6))
        for kw in KEYWORDS:
            if kw in trends_daily.columns:
                plt.plot(trends_daily.index, trends_daily[kw], label=kw)
            else:
                print(f"[WARN] keyword missing in trends_daily: {kw}")
        plt.legend()
        plt.title("Google Trends (daily) - specified keywords")
        plt.xlabel("Date")
        plt.ylabel("Interest (0-100)")
        plt.xticks(rotation=30)
        plt.tight_layout()
        plt.savefig(OUT_TRENDS)
        plt.close()
        print(f"[INFO] saved trends plot: {OUT_TRENDS}")

    print("[INFO] Done.")
    return 0

if __name__ == "__main__":
    exit(main())
