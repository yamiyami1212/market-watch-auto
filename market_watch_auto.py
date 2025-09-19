import time
import matplotlib.pyplot as plt  # ← 最初にまとめて import する

# （中略：データ取得部分）

if df is None or df.empty:
    print("⚠️ Could not fetch Google Trends data.")
else:
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

    # グラフを保存（必ず trend.png として出力）
    plt.savefig("trend.png")
    print("✅ Graph saved as trend.png")
