import os
import pandas as pd
import matplotlib.pyplot as plt
from pytrends.request import TrendReq
from datetime import datetime

# keywords
KEYWORDS = [
    "Borrow against stock",
    "Borrow against life insurance",
    "Sell my rolex watch",
    "Bankruptcy lawyer",
    "Sell my house fast",
    "Give car back"
]

# file names
CSV_FILE = "market_watch_data.csv"
IMG_FILE = "market_watch_chart.png"

# set up pytrends
pytrends = TrendReq(hl="en-US", tz=360)

# get last 6 months data
pytrends.build_payload(KEYWORDS, timeframe="today 6-m")
data = pytrends.interest_over_time().drop(columns=["isPartial"])

# add timestamp
data["timestamp"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# save to csv
if os.path.exists(CSV_FILE):
    old = pd.read_csv(CSV_FILE)
    combined = pd.concat([old, data.reset_index()])
    combined.drop_duplicates(subset=["date"], keep="last", inplace=True)
else:
    combined = data.reset_index()

combined.to_csv(CSV_FILE, index=False)

# plot chart
plt.figure(figsize=(12, 6))
for col in KEYWORDS:
    plt.plot(combined["date"], combined[col], label=col)

plt.title("Google Trends - Last 6 Months")
plt.xlabel("Date")
plt.ylabel("Interest")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(IMG_FILE)
