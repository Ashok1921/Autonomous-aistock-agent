"""
Diagnostic: print RAW dividend-related fields from yfinance's .info
for a handful of tickers, so we can see the actual pattern before
patching pct() again.
"""

import yfinance as yf

symbols = ["TCS", "RELIANCE", "INFY", "HDFCBANK", "ITC"]

fields = [
    "dividendYield",
    "trailingAnnualDividendYield",
    "trailingAnnualDividendRate",
    "dividendRate",
    "fiveYearAvgDividendYield",
]

for symbol in symbols:
    ticker = yf.Ticker(f"{symbol}.NS")
    info = ticker.info
    print(f"\n{symbol}:")
    for f in fields:
        print(f"  {f}: {info.get(f)}")