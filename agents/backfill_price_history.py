"""
Backfill price_history from yfinance.

Fetches recent daily OHLCV data for one or more symbols and inserts any
rows not already present in price_history (dedup on stock_id + timestamp).

Mirrors the .NS/.BO fallback pattern used in agents/technical_agent.py.

Run as: python -m agents.backfill_price_history TCS RELIANCE INFY HDFCBANK ITC
(defaults to TCS if no symbols given)
"""

import sys
import yfinance as yf
from sqlalchemy import create_engine, text

from config import DATABASE_URL
from agents.technical_agent import get_or_create_stock

engine = create_engine(DATABASE_URL)


def fetch_ohlcv(symbol: str, period: str = "6mo"):
    """Try NSE (.NS) first, fall back to BSE (.BO). Returns a yfinance DataFrame."""
    for suffix in (".NS", ".BO"):
        ticker = yf.Ticker(symbol + suffix)
        df = ticker.history(period=period)
        if not df.empty:
            return df
    return None


def backfill_symbol(symbol: str, period: str = "6mo") -> int:
    stock_id = get_or_create_stock(symbol)
    df = fetch_ohlcv(symbol, period=period)
    if df is None or df.empty:
        print(f"  {symbol}: no data returned from yfinance, skipped")
        return 0

    inserted = 0
    with engine.connect() as conn:
        for ts, row in df.iterrows():
            existing = conn.execute(text("""
                SELECT 1 FROM price_history WHERE stock_id = :sid AND timestamp = :ts
            """), {"sid": stock_id, "ts": ts.to_pydatetime()}).first()
            if existing:
                continue
            conn.execute(text("""
                INSERT INTO price_history (stock_id, timestamp, open, high, low, close, volume)
                VALUES (:sid, :ts, :open, :high, :low, :close, :volume)
            """), {
                "sid": stock_id,
                "ts": ts.to_pydatetime(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            })
            inserted += 1
        conn.commit()

    print(f"  {symbol}: inserted {inserted} new rows (stock_id={stock_id})")
    return inserted


if __name__ == "__main__":
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["TCS"]
    print(f"Backfilling price_history for: {', '.join(symbols)}")
    total = 0
    for sym in symbols:
        total += backfill_symbol(sym)
    print(f"Done. {total} total rows inserted.")