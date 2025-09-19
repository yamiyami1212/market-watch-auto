import time
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq

# -----------------------------
# 設定
# -----------------------------
KEYWORDS = ["Bitcoin", "Ethereum", "NFT"]

# GitHub Actions 対策: User-Agent を指定
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

# -----------------------------
# データ取得
# -----------------------------
# まず1年分を取得
pytrends.build_payload(KEYWORDS, timeframe="today 12-m")
df = pytrends.interest_over_time()

# 直近半年だけにフィルタリング
six_months_ago = pd.Timestamp.today() - pd.DateOffset(months=6)
df = df[df.index >= six_months_ago]

# -----------------------------
# 保存
# -----------------------------
csv_filename = "trend_data.csv"
df.to_csv(csv_filename)

# -----------------------------
# グラフ作成
# -----------------------------
plt.figure(figsize=(10, 6))
for kw in KEYWORDS
