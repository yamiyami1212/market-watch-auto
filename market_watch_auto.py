import time
import matplotlib.pyplot as plt
import pandas as pd
from pytrends.request import TrendReq

# CONFIG: set keywords and timeframe
KEYWORDS = ["Bitcoin", "Apple", "Google"]
TIMEFRAME = "today 12-m"  # try "today 5-y" or "today 12-m"
GEO = ""  # "" for worldwide, or "US", "JP", etc.

pytrends = TrendReq(hl="en-US", tz=0)

# Try to fetch data with retries
df = None
for attempt in range(3):
    try:
        pytrends.build_payload(KEYWORDS, timeframe=TIMEFRAME, geo=GEO)
        df = pytrends.interest_over_time()
        print("✅ Google Trends data fetched")
        break
    except Exception as e:
        print(f"⚠️ Attempt {attempt+1} failed: {e}")
        time.sleep(5)

# Save debug CSV and create PNG (plot or placeholder)
if df is None or df.empty:
    print("⚠️ No data retrieved from Google Trends.")
    # Create CSV with note for debugging
    debug_df = pd.DataFrame({"note": ["No data from Google Trends for given keywords/timeframe/geo"]})
    debug_df.to_csv("data.csv", index=False)
    # Create placeholder image
    plt.figure(figsize=(6, 4))
    plt.text(0.5, 0.5, "No data", fontsize=24, ha="center", va="center")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig("trend.png")
    print("✅ Placeholder saved as trend.png and data.csv created")
else:
    # Clean and save CSV for inspection
    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"], errors="ignore")
    df = df.dropna(how="all")
    df.to_csv("data.csv")
    print(f"✅ Data saved to data.csv, shape={df.shape}")
    # Plot
    plt.figure(figsize=(10, 6))
    for kw in KEYWORDS:
        if kw in df.columns:
            plt.plot(df.index, df[kw], label=kw)
        else:
            print(f"⚠️ Column for '{kw}' not in dataframe")
    plt.legend()
    plt.title("Google Trends")
    plt.xlabel("Date")
    plt.ylabel("Interest")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("trend.png")
    print("✅ Plot saved as trend.png")
