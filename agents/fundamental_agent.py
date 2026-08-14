import yfinance as yf
from datetime import datetime
from sqlalchemy import create_engine, text
from crewai.tools import tool
from config import DATABASE_URL

from agents.technical_agent import get_or_create_stock  # reuse existing helper

engine = create_engine(DATABASE_URL)


def _compute_roe_roa_fallback(ticker):
    """Compute ROE/ROA manually from raw financials when .info lacks them."""
    try:
        financials = ticker.financials
        balance_sheet = ticker.balance_sheet
        if financials.empty or balance_sheet.empty:
            return None, None

        net_income = financials.loc["Net Income"].iloc[0]
        total_equity = balance_sheet.loc["Stockholders Equity"].iloc[0]
        total_assets = balance_sheet.loc["Total Assets"].iloc[0]

        roe = round(float(net_income) / float(total_equity) * 100, 2) if total_equity else None
        roa = round(float(net_income) / float(total_assets) * 100, 2) if total_assets else None
        return roe, roa
    except Exception:
        return None, None


def _compute_current_ratio_fallback(ticker):
    """Compute current ratio manually from balance sheet."""
    try:
        balance_sheet = ticker.balance_sheet
        if balance_sheet.empty:
            return None
        current_assets = balance_sheet.loc["Current Assets"].iloc[0]
        current_liabilities = balance_sheet.loc["Current Liabilities"].iloc[0]
        return round(float(current_assets) / float(current_liabilities), 2) if current_liabilities else None
    except Exception:
        return None


def _compute_free_cashflow_fallback(ticker):
    """Compute free cash flow manually: Operating Cash Flow - CapEx."""
    try:
        cashflow = ticker.cashflow
        if cashflow.empty:
            return None
        operating_cf = cashflow.loc["Operating Cash Flow"].iloc[0]
        capex = cashflow.loc["Capital Expenditure"].iloc[0]  # usually negative already
        return float(operating_cf) + float(capex)
    except Exception:
        return None


def fetch_fundamentals(symbol: str) -> dict:
    """
    Fetch fundamental data for a stock using yfinance's .info dict.
    Tries .NS (NSE) first, falls back to .BO (BSE) — same pattern as technical_agent.
    Falls back to computing ROE/ROA/current_ratio/free_cashflow manually from
    raw financial statements when .info doesn't have them (common for Indian tickers).
    """
    ticker = None
    for suffix in (".NS", ".BO"):
        candidate = yf.Ticker(f"{symbol}{suffix}")
        info = candidate.info
        if info and info.get("regularMarketPrice") is not None:
            ticker = candidate
            break
    if ticker is None:
        raise ValueError(f"No fundamental data found for {symbol} on NSE or BSE")

    def pct(x):
        if not isinstance(x, (int, float)):
            return None
        # yfinance inconsistently returns some yields/margins as a fraction
        # (0.0265) and others already as a percent (2.65) — treat anything
        # over 1 as already a percent.
        return round(x, 2) if x > 1 else round(x * 100, 2)

    roe = pct(info.get("returnOnEquity"))
    roa = pct(info.get("returnOnAssets"))
    current_ratio = info.get("currentRatio")
    free_cashflow = info.get("freeCashflow")

    # Fall back to computing from raw financials when .info is missing these
    # (common gap for Indian NSE/BSE tickers via yfinance)
    if roe is None or roa is None:
        fallback_roe, fallback_roa = _compute_roe_roa_fallback(ticker)
        roe = roe if roe is not None else fallback_roe
        roa = roa if roa is not None else fallback_roa

    if current_ratio is None:
        current_ratio = _compute_current_ratio_fallback(ticker)

    if free_cashflow is None:
        free_cashflow = _compute_free_cashflow_fallback(ticker)

    return {
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "eps": info.get("trailingEps"),
        "peg_ratio": info.get("pegRatio"),
        "debt_to_equity": info.get("debtToEquity"),
        "roe": roe,
        "roa": roa,
        "market_cap": info.get("marketCap"),
        # dividendYield from yfinance is already a percent (e.g. 2.65 = 2.65%) — don't run through pct()
        "dividend_yield": round(info.get("dividendYield"), 2) if isinstance(info.get("dividendYield"), (int, float)) else None,
        "book_value": info.get("bookValue"),
        "price_to_book": info.get("priceToBook"),
        "revenue_growth": pct(info.get("revenueGrowth")),
        "profit_margin": pct(info.get("profitMargins")),
        "current_ratio": current_ratio,
        "free_cashflow": free_cashflow,
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