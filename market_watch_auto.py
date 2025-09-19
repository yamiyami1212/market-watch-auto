import time
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq

# -----------------------------
# 設定
# -----------------------------
KEYWORDS = ["Bitcoin", "Ethereum", "NFT"]

# Google Trends に接続（User-Agent と retries を強化）
pytrends = TrendReq(
    hl="en-US",
    tz=360,
    retries=5,
    backoff_factor=0.5,
    requests_args={
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
    },
)

# -----------------------------
# データ取得（リトライつき）
# -----------------------------
success = False
for attempt in range(3):
    try:
        pytrends.build_payload(KEYWORDS, timeframe="today 6-m")
        df = pytrends.interest_over_time()
        success = True
        break
    except Exception as e:
        print(f"⚠️ Attempt {attempt+1} failed: {e}")
        time.sleep(5)

if not success:
    raise RuntimeError("❌ Google Trends API request failed after 3 attempts.")

# NaN があれば削除
df = df.dropna()

# -----------------------------
# グラフ描画
# -----------------------------
plt.figure(figsize=(10, 6))
for kw in KEYWORDS:
    plt.plot(df.index, df[kw], label=kw)

plt.legend()
plt.title("Google Trends: Last 6 Months")
plt.xlabel("Date")
plt.ylabel("Search Interest")
plt.grid(True)
plt.tight_layout()
plt.savefig("trend.png")

print("✅ グラフを trend.png として保存しました。")
