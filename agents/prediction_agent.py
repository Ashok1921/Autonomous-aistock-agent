"""
Prediction Agent
Trains a Random Forest on a stock's own price history to predict tomorrow's
% price change, derives a direction call, and saves to the `predictions` table.

Run as: python -m agents.prediction_agent   (from project root)
"""

import numpy as np
import pandas as pd
import yfinance as yf
import ta
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sqlalchemy import create_engine, text
from crewai.tools import tool
from config import DATABASE_URL

from agents.technical_agent import get_or_create_stock  # reuse existing helper

engine = create_engine(DATABASE_URL)

FEATURE_COLUMNS = [
    "sma_20", "ema_20", "rsi_14", "macd", "macd_signal",
    "bollinger_upper", "bollinger_lower", "atr",
    "return_1d", "return_5d", "volume_change",
]


def fetch_training_data(symbol: str, period: str = "2y") -> pd.DataFrame:
    """Pull historical OHLCV for training. Tries .NS then .BO, same as technical_agent."""
    ticker_ns = f"{symbol}.NS"
    df = yf.Ticker(ticker_ns).history(period=period)
    if df.empty:
        df = yf.Ticker(f"{symbol}.BO").history(period=period)
        if df.empty:
            raise ValueError(f"No historical data found for {symbol} on NSE or BSE")
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute technical indicators (same set as Technical Agent) plus a few
    extra momentum/volume features, and the next-day % change target.
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

    df["return_1d"] = df["Close"].pct_change(1)
    df["return_5d"] = df["Close"].pct_change(5)
    df["volume_change"] = df["Volume"].pct_change(1)

    # Target: next day's % change in Close (what we're trying to predict)
    df["target_next_change_pct"] = df["Close"].shift(-1) / df["Close"] - 1
    
    # Some days have zero volume (market holidays, thin trading), which makes
    # pct_change() produce +/-inf. Convert those to NaN so dropna() catches them.
    df = df.replace([np.inf, -np.inf], np.nan)

    return df


def train_and_predict(symbol: str, horizon: str = "1d") -> dict:
    """
    Train a Random Forest on a stock's history and predict the next period's
    % change. Returns direction, predicted % change, and a confidence score.
    """
    raw = fetch_training_data(symbol)
    data = build_features(raw)

    # Drop rows with NaNs (early rows without enough history, and the very
    # last row which has no "next day" target yet — that's our prediction row)
    train_data = data.dropna(subset=FEATURE_COLUMNS + ["target_next_change_pct"])

    X = train_data[FEATURE_COLUMNS]
    y = train_data["target_next_change_pct"]

    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)

    # Time-series cross-validation (no shuffling — respects chronological order).
    # Confidence = directional accuracy: of the days in each held-out fold, what
    # fraction did the model correctly call as up vs down? More interpretable
    # than R² for a noisy daily-return target.
    tscv = TimeSeriesSplit(n_splits=5)
    fold_accuracies = []
    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        fold_model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
        fold_model.fit(X_train, y_train)
        preds = fold_model.predict(X_test)

        correct_direction = np.sign(preds) == np.sign(y_test.values)
        fold_accuracies.append(correct_direction.mean())

    confidence = round(float(np.mean(fold_accuracies)), 3)

    model.fit(X, y)

    # Predict using the most recent row (which has features but no target yet)
    latest_features = data[FEATURE_COLUMNS].dropna().iloc[[-1]]
    predicted_change = float(model.predict(latest_features)[0])
    predicted_change_pct = round(predicted_change * 100, 2)

    if predicted_change_pct > 0.3:
        direction = "up"
    elif predicted_change_pct < -0.3:
        direction = "down"
    else:
        direction = "flat"

    target_date = (pd.Timestamp.now() + pd.Timedelta(days=1)).date()

    return {
        "model_name": "RandomForest_v1",
        "horizon": horizon,
        "predicted_direction": direction,
        "predicted_change_pct": predicted_change_pct,
        "confidence": confidence,
        "target_date": target_date,
    }


def save_prediction(stock_id: int, prediction: dict):
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO predictions
                    (stock_id, model_name, horizon, predicted_direction,
                     predicted_change_pct, confidence, target_date)
                VALUES
                    (:stock_id, :model_name, :horizon, :predicted_direction,
                     :predicted_change_pct, :confidence, :target_date)
            """),
            {**prediction, "stock_id": stock_id}
        )
        conn.commit()


def get_prediction_summary(symbol: str, horizon: str = "1d") -> dict:
    prediction = train_and_predict(symbol, horizon)
    stock_id = get_or_create_stock(symbol)
    save_prediction(stock_id, prediction)
    return prediction


@tool("Prediction Tool")
def prediction_tool(symbol: str) -> str:
    """
    Trains a Random Forest model on a stock's historical prices and technical
    indicators, predicts tomorrow's likely direction and % price change, saves
    the prediction to the database, and returns a summary.
    """
    result = get_prediction_summary(symbol)
    return (
        f"Prediction for {symbol} (horizon: {result['horizon']}):\n"
        f"  Direction: {result['predicted_direction']}\n"
        f"  Predicted change: {result['predicted_change_pct']}%\n"
        f"  Confidence (CV R²): {result['confidence']}\n"
        f"  Target date: {result['target_date']}"
    )


if __name__ == "__main__":
    symbol = "TCS"
    result = get_prediction_summary(symbol)
    print(f"Prediction for {symbol}:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("\nSaved to database.")