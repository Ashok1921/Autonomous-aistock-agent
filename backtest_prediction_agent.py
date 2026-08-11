"""
Backtesting harness for the Prediction Agent.

Walks forward through a stock's history: for each day (after an initial
training window), trains on everything before it, predicts that day's %
change, and compares to what actually happened. Repeats across multiple
stocks to avoid drawing conclusions from a single ticker.

This does NOT touch the `predictions` table — it's a standalone evaluation
script, not something that runs as part of the live pipeline.

Run as: python backtest_prediction_agent.py   (from project root)
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from agents.prediction_agent import fetch_training_data, build_features, FEATURE_COLUMNS

SYMBOLS = ["TCS", "RELIANCE", "INFY", "HDFCBANK", "ITC"]
MIN_TRAIN_DAYS = 180   # need enough history before the first backtest prediction
STEP = 5               # re-train every N days instead of every single day (much faster)


def backtest_symbol(symbol: str) -> pd.DataFrame:
    """
    Walk-forward backtest for one symbol. Returns a DataFrame of
    date, actual_change_pct, predicted_change_pct, correct_direction.
    """
    raw = fetch_training_data(symbol, period="2y")
    data = build_features(raw)
    data = data.dropna(subset=FEATURE_COLUMNS + ["target_next_change_pct"])

    if len(data) < MIN_TRAIN_DAYS + STEP:
        print(f"  Skipping {symbol}: not enough history ({len(data)} usable rows)")
        return pd.DataFrame()

    results = []
    X_all = data[FEATURE_COLUMNS]
    y_all = data["target_next_change_pct"]
    dates = data.index

    for i in range(MIN_TRAIN_DAYS, len(data) - 1, STEP):
        X_train, y_train = X_all.iloc[:i], y_all.iloc[:i]
        X_test, y_test = X_all.iloc[[i]], y_all.iloc[i]

        model = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
        model.fit(X_train, y_train)
        pred = model.predict(X_test)[0]

        results.append({
            "symbol": symbol,
            "date": dates[i],
            "actual_change_pct": round(y_test * 100, 2),
            "predicted_change_pct": round(pred * 100, 2),
            "correct_direction": int(np.sign(pred) == np.sign(y_test)),
        })

    return pd.DataFrame(results)


def run_backtest():
    all_results = []
    for symbol in SYMBOLS:
        print(f"Backtesting {symbol}...")
        df = backtest_symbol(symbol)
        if not df.empty:
            all_results.append(df)

    if not all_results:
        print("No results — check data availability.")
        return

    combined = pd.concat(all_results, ignore_index=True)

    print("\n" + "=" * 60)
    print("BACKTEST SUMMARY (per stock)")
    print("=" * 60)
    per_stock = combined.groupby("symbol").agg(
        num_predictions=("correct_direction", "count"),
        directional_accuracy=("correct_direction", "mean"),
        mean_abs_error_pct=("predicted_change_pct", lambda s: (
            (s - combined.loc[s.index, "actual_change_pct"]).abs().mean()
        )),
    )
    per_stock["directional_accuracy"] = per_stock["directional_accuracy"].round(3)
    per_stock["mean_abs_error_pct"] = per_stock["mean_abs_error_pct"].round(3)
    print(per_stock)

    print("\n" + "=" * 60)
    print("BACKTEST SUMMARY (overall)")
    print("=" * 60)
    overall_accuracy = combined["correct_direction"].mean()
    overall_mae = (combined["predicted_change_pct"] - combined["actual_change_pct"]).abs().mean()
    print(f"Total predictions: {len(combined)}")
    print(f"Overall directional accuracy: {round(overall_accuracy, 3)}  (0.5 = coin flip)")
    print(f"Overall mean absolute error: {round(overall_mae, 3)}%")

    combined.to_csv("backtest_results.csv", index=False)
    print("\nFull results saved to backtest_results.csv")


if __name__ == "__main__":
    run_backtest()