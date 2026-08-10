import yfinance as yf
from datetime import datetime
from sqlalchemy import create_engine, text
from crewai.tools import tool
from config import DATABASE_URL

from agents.technical_agent import get_or_create_stock  # reuse existing helper

engine = create_engine(DATABASE_URL)


def fetch_fundamentals(symbol: str) -> dict:
    """
    Fetch fundamental data for a stock using yfinance's .info dict.
    Tries .NS (NSE) first, falls back to .BO (BSE) — same pattern as technical_agent.
    """
    for suffix in (".NS", ".BO"):
        ticker = yf.Ticker(f"{symbol}{suffix}")
        info = ticker.info
        if info and info.get("regularMarketPrice") is not None:
            break
    else:
        raise ValueError(f"No fundamental data found for {symbol} on NSE or BSE")

    def pct(x):
        if not isinstance(x, (int, float)):
            return None
        # yfinance inconsistently returns some yields/margins as a fraction
        # (0.0265) and others already as a percent (2.65) — treat anything
        # over 1 as already a percent.
        return round(x, 2) if x > 1 else round(x * 100, 2)

    return {
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "eps": info.get("trailingEps"),
        "peg_ratio": info.get("pegRatio"),
        "debt_to_equity": info.get("debtToEquity"),
        "roe": pct(info.get("returnOnEquity")),
        "roa": pct(info.get("returnOnAssets")),
        "market_cap": info.get("marketCap"),
        # dividendYield from yfinance is already a percent (e.g. 2.65 = 2.65%) — don't run through pct()
        "dividend_yield": round(info.get("dividendYield"), 2) if isinstance(info.get("dividendYield"), (int, float)) else None,
        "book_value": info.get("bookValue"),
        "price_to_book": info.get("priceToBook"),
        "revenue_growth": pct(info.get("revenueGrowth")),
        "profit_margin": pct(info.get("profitMargins")),
        "current_ratio": info.get("currentRatio"),
        "free_cashflow": info.get("freeCashflow"),
    }


def save_fundamentals(stock_id: int, data: dict):
    """
    Save a fundamentals snapshot into the fundamentals table.
    One row per (stock_id, fetched_at) — same upsert style as save_indicators.
    """
    fetched_at = datetime.now()
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO fundamentals
                    (stock_id, pe_ratio, forward_pe, eps, peg_ratio,
                     debt_to_equity, roe, roa, market_cap, dividend_yield,
                     book_value, price_to_book, revenue_growth, profit_margin,
                     current_ratio, free_cashflow, fetched_at)
                VALUES
                    (:stock_id, :pe_ratio, :forward_pe, :eps, :peg_ratio,
                     :debt_to_equity, :roe, :roa, :market_cap, :dividend_yield,
                     :book_value, :price_to_book, :revenue_growth, :profit_margin,
                     :current_ratio, :free_cashflow, :fetched_at)
                ON CONFLICT (stock_id, fetched_at) DO UPDATE SET
                    pe_ratio = EXCLUDED.pe_ratio,
                    forward_pe = EXCLUDED.forward_pe,
                    eps = EXCLUDED.eps,
                    peg_ratio = EXCLUDED.peg_ratio,
                    debt_to_equity = EXCLUDED.debt_to_equity,
                    roe = EXCLUDED.roe,
                    roa = EXCLUDED.roa,
                    market_cap = EXCLUDED.market_cap,
                    dividend_yield = EXCLUDED.dividend_yield,
                    book_value = EXCLUDED.book_value,
                    price_to_book = EXCLUDED.price_to_book,
                    revenue_growth = EXCLUDED.revenue_growth,
                    profit_margin = EXCLUDED.profit_margin,
                    current_ratio = EXCLUDED.current_ratio,
                    free_cashflow = EXCLUDED.free_cashflow
            """),
            {**data, "stock_id": stock_id, "fetched_at": fetched_at}
        )
        conn.commit()


def get_fundamentals_summary(symbol: str) -> dict:
    """Fetch + save fundamentals for a symbol, return the raw dict."""
    data = fetch_fundamentals(symbol)
    stock_id = get_or_create_stock(symbol)
    save_fundamentals(stock_id, data)
    return data


@tool("Fundamental Analysis Tool")
def fundamental_analysis_tool(symbol: str) -> str:
    """
    Fetches key fundamental ratios (P/E, EPS, ROE, debt-to-equity, profit margin,
    revenue growth, etc.) for an Indian stock symbol (e.g. 'TCS', 'RELIANCE'),
    saves them to the database, and returns a formatted summary.
    """
    data = get_fundamentals_summary(symbol)
    lines = [f"Fundamental analysis for {symbol}:"]
    for k, v in data.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


if __name__ == "__main__":
    symbol = "TCS"
    result = get_fundamentals_summary(symbol)
    print(f"Fundamentals for {symbol}:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("\nSaved to database.")