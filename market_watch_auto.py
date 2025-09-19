import time
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq

# ---------------------------------
# 設定
# ---------------------------------
KEYWORDS = ["Bitcoin", "Ethereum", "NFT"]

# GitHub Actions 対策: User-Agent を指定してリクエスト
pytrends = TrendReq(
    hl="en-US",
    tz=360,
    requests_args={
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
    },
)

# ---------------------------------
# データ取得
# ---------------------------------
pytrends.build_payload(KEYWORDS, timeframe="today 6-m")
df = pytrends.interest_over_time()

# NaN があれば削除
df = df.dropna()

# ---------------------------------
# グラフ描画
# ---------------------------------
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
