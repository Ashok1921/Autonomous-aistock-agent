import yfinance as yf
import pandas as pd
import ta
from sqlalchemy import create_engine, text
from crewai.tools import tool
from config import DATABASE_URL


engine = create_engine(DATABASE_URL)

def fetch_price_data(symbol: str, period: str = "3mo") -> pd.DataFrame:
    """
    Fetch OHLCV data for a stock symbol.
    Tries .NS (NSE) first, falls back to .BO (BSE) if no data.
    """
    ticker_ns = f"{symbol}.NS"
    df = yf.Ticker(ticker_ns).history(period=period)

    if df.empty:
        ticker_bo = f"{symbol}.BO"
        df = yf.Ticker(ticker_bo).history(period=period)
        if df.empty:
            raise ValueError(f"No data found for {symbol} on NSE or BSE")

    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute SMA, EMA, RSI, MACD, Bollinger Bands, and ATR
    and append them as columns to the price DataFrame.
    """
    df = df.copy()

    df["sma_20"] = ta.trend.sma_indicator(df["Close"], window=20)
    df["ema_20"] = ta.trend.ema_indicator(df["Close"], window=20)
    df["rsi_14"] = ta.momentum.rsi(df["Close"], window=14)

    macd = ta.trend.MACD(df["Close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    bollinger = ta.volatility.BollingerBands(df["Close"])
    df["bollinger_upper"] = bollinger.bollinger_hband()
    df["bollinger_lower"] = bollinger.bollinger_lband()

    df["atr"] = ta.volatility.average_true_range(
        df["High"], df["Low"], df["Close"], window=14
    )

    return df


def get_latest_signal(df: pd.DataFrame) -> dict:
    """
    Return the most recent row's indicator values plus a simple
    bullish/bearish/neutral signal based on RSI + MACD.
    """
    latest = df.iloc[-1]

    if latest["rsi_14"] > 70:
        rsi_signal = "overbought"
    elif latest["rsi_14"] < 30:
        rsi_signal = "oversold"
    else:
        rsi_signal = "neutral"

    macd_signal = "bullish" if latest["macd"] > latest["macd_signal"] else "bearish"

    return {
        "date": str(latest.name),
        "close": round(latest["Close"], 2),
        "sma_20": round(latest["sma_20"], 2),
        "ema_20": round(latest["ema_20"], 2),
        "rsi_14": round(latest["rsi_14"], 2),
        "rsi_signal": rsi_signal,
        "macd": round(latest["macd"], 4),
        "macd_signal_line": round(latest["macd_signal"], 4),
        "macd_signal": macd_signal,
        "atr": round(latest["atr"], 2),
    }
    
def get_or_create_stock(symbol: str, exchange: str = "NSE") -> int:
    """
    Ensure the stock exists in the stocks table, return its id.
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM stocks WHERE symbol = :symbol"),
            {"symbol": symbol}
        ).fetchone()

        if result:
            return result[0]

        result = conn.execute(
            text("""
                INSERT INTO stocks (symbol, exchange)
                VALUES (:symbol, :exchange)
                RETURNING id
            """),
            {"symbol": symbol, "exchange": exchange}
        )
        conn.commit()
        return result.fetchone()[0]
    
    
def save_indicators(stock_id: int, df: pd.DataFrame):
    """
    Save all computed indicator rows into technical_indicators,
    skipping duplicates (same stock_id + timestamp).
    """
    with engine.connect() as conn:
        for timestamp, row in df.iterrows():
            if pd.isna(row["sma_20"]):  # skip early rows without enough history
                continue

            conn.execute(
                text("""
                    INSERT INTO technical_indicators
                        (stock_id, timestamp, sma_20, ema_20, rsi_14, macd, macd_signal,
                         bollinger_upper, bollinger_lower, atr)
                    VALUES
                        (:stock_id, :timestamp, :sma_20, :ema_20, :rsi_14, :macd, :macd_signal,
                         :bollinger_upper, :bollinger_lower, :atr)
                    ON CONFLICT (stock_id, timestamp) DO UPDATE SET
                        sma_20 = EXCLUDED.sma_20,
                        ema_20 = EXCLUDED.ema_20,
                        rsi_14 = EXCLUDED.rsi_14,
                        macd = EXCLUDED.macd,
                        macd_signal = EXCLUDED.macd_signal,
                        bollinger_upper = EXCLUDED.bollinger_upper,
                        bollinger_lower = EXCLUDED.bollinger_lower,
                        atr = EXCLUDED.atr
                """),
                {
                    "stock_id": stock_id,
                    "timestamp": timestamp.to_pydatetime(),
                    "sma_20": float(row["sma_20"]),
                    "ema_20": float(row["ema_20"]),
                    "rsi_14": float(row["rsi_14"]),
                    "macd": float(row["macd"]),
                    "macd_signal": float(row["macd_signal"]),
                    "bollinger_upper": float(row["bollinger_upper"]) if not pd.isna(row["bollinger_upper"]) else None,
                    "bollinger_lower": float(row["bollinger_lower"]) if not pd.isna(row["bollinger_lower"]) else None,
                    "atr": float(row["atr"]) if not pd.isna(row["atr"]) else None,
                }
            )
        conn.commit()  
        
        
@tool("Technical Analysis Tool")
def technical_analysis_tool(symbol: str) -> str:
    """
    Fetches price data for a stock symbol, computes technical indicators
    (SMA, EMA, RSI, MACD, ATR), saves them to the database, and returns
    a summary of the latest signal.
    """
    data = fetch_price_data(symbol)
    data_with_indicators = compute_indicators(data)
    signal = get_latest_signal(data_with_indicators)

    stock_id = get_or_create_stock(symbol)
    save_indicators(stock_id, data_with_indicators)

    return (
        f"Technical analysis for {symbol} as of {signal['date']}:\n"
        f"Close: {signal['close']}, SMA-20: {signal['sma_20']}, EMA-20: {signal['ema_20']}\n"
        f"RSI-14: {signal['rsi_14']} ({signal['rsi_signal']})\n"
        f"MACD: {signal['macd']} vs Signal Line: {signal['macd_signal_line']} ({signal['macd_signal']})\n"
        f"ATR: {signal['atr']}"
    )          

    

if __name__ == "__main__":
    symbol = "TCS"
    data = fetch_price_data(symbol)
    data_with_indicators = compute_indicators(data)

    signal = get_latest_signal(data_with_indicators)
    print("Latest Signal:")
    for k, v in signal.items():
        print(f"  {k}: {v}")

    stock_id = get_or_create_stock(symbol)
    save_indicators(stock_id, data_with_indicators)
    print(f"\nSaved indicators for {symbol} (stock_id={stock_id}) to database.")