# market_watch_trends.py
# Replace the file entirely with this content.

import time
import sys
import traceback
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq

# ---- 設定（ここをそのまま使います） ----
KEYWORDS = [
    "sell my house fast",
    "give car back",
    "borrow against life insurance",
    "sell my rolex watch",
    "bankruptcy lawyer",
]

# timezone and user-agent for GitHub Actions
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)

OUT_CSV = "trends_data.csv"
OUT_PNG = "trends_graph.png"

def fetch_trends(keywords, timeframes):
    """複数のtimeframeを試して、空でないデータを返す。失敗時はNoneを返す。"""
    pytrends = TrendReq(hl="en-US", tz=360, requests_args={"headers": {"User-Agent": USER_AGENT}})
    for tf in timeframes:
        try:
            print(f"Trying timeframe: {tf}", flush=True)
            pytrends.build_payload(keywords, timeframe=tf)
            df = pytrends.interest_over_time()
            if df is None or df.empty:
                print(" -> empty result", flush=True)
                continue
            # drop isPartial column if present
            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])
            return df
        except Exception as e:
            print(f"Exception while fetching timeframe {tf}: {e}", flush=True)
            traceback.print_exc()
            time.sleep(2)
    return None

def save_csv(df, path):
    df.to_csv(path, index=True)
    print(f"Saved CSV: {path} (rows={len(df)})", flush=True)

def plot_trends(df, keywords, out_png):
    plt.figure(figsize=(12,5))
    for kw in keywords:
        if kw in df.columns:
            plt.plot(df.index, df[kw], label=kw)
    plt.title("Google Trends (daily) - specified keywords")
    plt.xlabel("Date")
    plt.ylabel("Interest (0-100)")
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()
    print(f"Saved PNG: {out_png}", flush=True)

def make_empty_placeholder_png(path, message="No trends data"):
    plt.figure(figsize=(8,4))
    plt.text(0.5, 0.5, message, ha='center', va='center', fontsize=20)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Saved placeholder PNG: {path}", flush=True)

def main():
    # pytrends supports up to 5 keywords in one payload (we use exactly 5)
    # 試すtimeframes（空なら長い期間, それでもダメなら日次を短く）
    timeframes = ["today 6-m", "today 12-m", "today 3-m", "now 7-d"]
    df = fetch_trends(KEYWORDS, timeframes)

    if df is None or df.empty:
        print("⚠️ No trends data fetched for any timeframe. Writing placeholder outputs.", flush=True)
        # 空CSV作成（ヘッダのみ）
        empty_df = pd.DataFrame(columns=KEYWORDS)
        empty_df.to_csv(OUT_CSV, index=True)
        make_empty_placeholder_png(OUT_PNG, "No trends data")
        sys.exit(0)  # 成功終了（ワークフローは続行させたい場合）
    else:
        # 日次 -> 季月平均など必要ならここで変換可能（今はそのまま保存）
        save_csv(df, OUT_CSV)
        plot_trends(df, KEYWORDS, OUT_PNG)
        sys.exit(0)

if __name__ == "__main__":
    main()
