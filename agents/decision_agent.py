"""
Decision Agent
--------------
Pulls the latest signals for a stock from:
  - technical_indicators (sma_20, ema_20, rsi_14, macd, macd_signal, atr, ...)
  - fundamentals (pe_ratio, roe, debt_to_equity, revenue_growth, ...)
  - sentiment_scores (score, confidence)
  - predictions (predicted_direction, predicted_change_pct, confidence)
  - price_history (latest close, for ATR% and stop-loss/target-price math)

Applies a hard-coded risk-rule engine to combine them into:
  - verdict: STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
  - stop_loss / target_price: ATR-based, only set for non-HOLD verdicts
  - signals_used: full jsonb trail (per-signal scores, weights, conviction, risk flags)

Wrapped as a CrewAI tool so the LLM agent can explain the decision in
natural language.

Run as: python -m agents.decision_agent  (from project root)
"""

from datetime import datetime, timedelta
from crewai.tools import tool
from sqlalchemy import create_engine, text

from config import DATABASE_URL
from agents.technical_agent import get_or_create_stock

from decimal import Decimal

engine = create_engine(DATABASE_URL)


def _row_to_float_dict(row) -> dict | None:
    """Convert a mapping row to a plain dict, casting Decimal/numeric values to float
    (Postgres numeric columns come back as decimal.Decimal, which doesn't mix with
    float arithmetic)."""
    if row is None:
        return None
    out = {}
    for k, v in dict(row).items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# 1. Fetch latest signals
# ---------------------------------------------------------------------------

def fetch_latest_signals(symbol: str) -> dict:
    """Pull the most recent row from each signal table for a stock."""
    stock_id = get_or_create_stock(symbol)
    signals = {"symbol": symbol, "stock_id": stock_id}

    with engine.connect() as conn:
        technical = conn.execute(text("""
            SELECT sma_20, ema_20, rsi_14, macd, macd_signal,
                   bollinger_upper, bollinger_lower, atr, timestamp
            FROM technical_indicators
            WHERE stock_id = :sid
            ORDER BY timestamp DESC LIMIT 1
        """), {"sid": stock_id}).mappings().first()

        fundamentals = conn.execute(text("""
            SELECT pe_ratio, forward_pe, eps, peg_ratio, debt_to_equity, roe, roa,
                   revenue_growth, profit_margin, current_ratio, free_cashflow, fetched_at
            FROM fundamentals
            WHERE stock_id = :sid
            ORDER BY fetched_at DESC LIMIT 1
        """), {"sid": stock_id}).mappings().first()

        sentiment = conn.execute(text("""
            SELECT score, confidence, computed_at
            FROM sentiment_scores
            WHERE stock_id = :sid
            ORDER BY computed_at DESC LIMIT 1
        """), {"sid": stock_id}).mappings().first()

        prediction = conn.execute(text("""
            SELECT predicted_direction, predicted_change_pct, confidence, target_date, predicted_at
            FROM predictions
            WHERE stock_id = :sid
            ORDER BY predicted_at DESC LIMIT 1
        """), {"sid": stock_id}).mappings().first()

        price_row = conn.execute(text("""
            SELECT close, timestamp
            FROM price_history
            WHERE stock_id = :sid
            ORDER BY timestamp DESC LIMIT 1
        """), {"sid": stock_id}).mappings().first()

    signals["technical"] = _row_to_float_dict(technical)
    signals["fundamentals"] = _row_to_float_dict(fundamentals)
    signals["sentiment"] = _row_to_float_dict(sentiment)
    signals["prediction"] = _row_to_float_dict(prediction)
    signals["latest_close"] = float(price_row["close"]) if price_row else None
    return signals


# ---------------------------------------------------------------------------
# 2. Risk-rule engine
# ---------------------------------------------------------------------------

# Base weights — Prediction is deliberately low given the 0.500 backtest accuracy.
WEIGHTS = {
    "fundamentals": 0.40,
    "technical": 0.25,
    "sentiment": 0.20,
    "prediction": 0.15,
}

STALE_HOURS = 48  # signal older than this is treated as unreliable


def _is_stale(row: dict | None, ts_field: str) -> bool:
    if not row or not row.get(ts_field):
        return True
    ts = row[ts_field]
    if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    return datetime.now() - ts > timedelta(hours=STALE_HOURS)


def _score_technical(row: dict | None) -> float | None:
    """Returns -1..+1, or None if unavailable."""
    if not row or row.get("rsi_14") is None or row.get("macd") is None:
        return None
    score = 0.0
    votes = 0

    rsi = row["rsi_14"]
    if rsi is not None:
        if rsi < 30:
            score += 1.0
        elif rsi > 70:
            score -= 1.0
        else:
            score += (50 - rsi) / 50 * -0.3  # mild pull toward neutral
        votes += 1

    if row.get("macd") is not None and row.get("macd_signal") is not None:
        score += 1.0 if row["macd"] > row["macd_signal"] else -1.0
        votes += 1

    if row.get("sma_20") is not None and row.get("ema_20") is not None:
        score += 1.0 if row["ema_20"] > row["sma_20"] else -1.0
        votes += 1

    return score / votes if votes else None


def _score_fundamentals(row: dict | None) -> tuple[float | None, bool]:
    """Returns (score -1..+1, missing_critical_data_flag)."""
    if not row:
        return None, True

    critical = ["pe_ratio", "roe", "debt_to_equity"]
    missing_critical = any(row.get(k) is None for k in critical)

    score = 0.0
    votes = 0
    if row.get("pe_ratio") is not None:
        score += 1.0 if 0 < row["pe_ratio"] < 25 else (-0.5 if row["pe_ratio"] >= 25 else -1.0)
        votes += 1
    if row.get("roe") is not None:
        score += 1.0 if row["roe"] > 15 else (-1.0 if row["roe"] < 5 else 0.0)
        votes += 1
    if row.get("debt_to_equity") is not None:
        score += 1.0 if row["debt_to_equity"] < 1 else (-1.0 if row["debt_to_equity"] > 2 else 0.0)
        votes += 1
    if row.get("revenue_growth") is not None:
        score += 1.0 if row["revenue_growth"] > 10 else (-1.0 if row["revenue_growth"] < 0 else 0.0)
        votes += 1

    return (score / votes if votes else None), missing_critical


def _score_sentiment(row: dict | None) -> float | None:
    if not row or row.get("score") is None:
        return None
    return max(-1.0, min(1.0, row["score"]))


def _score_prediction(row: dict | None) -> float | None:
    if not row or row.get("confidence") is None:
        return None
    if row["confidence"] < 0.55:
        return 0.0  # explicitly zero out low-confidence predictions — not a real edge
    direction = row.get("predicted_direction")
    magnitude = min(abs(row.get("predicted_change_pct") or 0) / 5, 1.0)
    if direction == "up":
        return magnitude
    elif direction == "down":
        return -magnitude
    return 0.0


def apply_risk_rules(signals: dict) -> dict:
    """Core rule engine. Returns verdict + stop_loss/target_price + full signal trail."""
    reasoning = []
    weights_used = {}
    weighted_sum = 0.0
    total_weight = 0.0

    tech_score = _score_technical(signals["technical"])
    fund_score, fund_missing_critical = _score_fundamentals(signals["fundamentals"])
    sent_score = _score_sentiment(signals["sentiment"])
    pred_score = _score_prediction(signals["prediction"])

    scores = {
        "technical": tech_score,
        "fundamentals": fund_score,
        "sentiment": sent_score,
        "prediction": pred_score,
    }
    stale_flags = {
        "technical": _is_stale(signals["technical"], "timestamp"),
        "fundamentals": _is_stale(signals["fundamentals"], "fetched_at"),
        "sentiment": _is_stale(signals["sentiment"], "computed_at"),
        "prediction": _is_stale(signals["prediction"], "predicted_at"),
    }

    for name, score in scores.items():
        if score is None:
            reasoning.append(f"{name}: no data available, excluded from decision")
            continue
        if stale_flags[name]:
            reasoning.append(f"{name}: data stale (>{STALE_HOURS}h old), weight halved")
            w = WEIGHTS[name] * 0.5
        else:
            w = WEIGHTS[name]
        weighted_sum += score * w
        total_weight += w
        weights_used[name] = w
        reasoning.append(f"{name}: score={score:.2f}, weight={w:.2f}")

    # --- Hard risk rules (can override the weighted score) ---
    conviction_cap = 1.0
    hard_flags = []

    if fund_missing_critical:
        conviction_cap = min(conviction_cap, 0.5)
        hard_flags.append("Critical fundamental data missing (PE/ROE/D-E) — conviction capped at moderate")

    if fund_score is not None and sent_score is not None and (fund_score * sent_score) < -0.3:
        conviction_cap = min(conviction_cap, 0.5)
        hard_flags.append("Fundamentals and sentiment strongly disagree — conviction dampened")

    tech_row = signals["technical"]
    atr_pct = None
    if tech_row and tech_row.get("atr") and signals.get("latest_close"):
        atr_pct = tech_row["atr"] / signals["latest_close"] * 100
        if atr_pct > 4:
            conviction_cap = min(conviction_cap, 0.6)
            hard_flags.append(f"High volatility (ATR {atr_pct:.1f}% of price) — conviction reduced")

    if total_weight > 0 and weights_used.get("prediction", 0) >= total_weight * 0.9:
        conviction_cap = min(conviction_cap, 0.3)
        hard_flags.append("Decision would rest almost entirely on Prediction Agent — capped low (known ~50% backtest accuracy)")

    raw_score = weighted_sum / total_weight if total_weight > 0 else 0.0
    conviction = min(abs(raw_score), conviction_cap)

    if total_weight == 0:
        verdict = "HOLD"
        conviction = 0.0
        hard_flags.append("No usable signals at all — defaulting to HOLD")
    elif raw_score > 0.5:
        verdict = "STRONG_BUY" if conviction > 0.6 else "BUY"
    elif raw_score > 0.15:
        verdict = "BUY" if conviction > 0.4 else "HOLD"
    elif raw_score < -0.5:
        verdict = "STRONG_SELL" if conviction > 0.6 else "SELL"
    elif raw_score < -0.15:
        verdict = "SELL" if conviction > 0.4 else "HOLD"
    else:
        verdict = "HOLD"

    # --- Stop-loss / target-price, ATR-based ---
    stop_loss = None
    target_price = None
    close = signals.get("latest_close")
    atr = tech_row.get("atr") if tech_row else None
    if close and atr and verdict != "HOLD":
        strong = verdict in ("STRONG_BUY", "STRONG_SELL")
        target_mult = 2.5 if strong else 1.5
        if verdict in ("BUY", "STRONG_BUY"):
            stop_loss = round(close - 1.5 * atr, 2)
            target_price = round(close + target_mult * atr, 2)
        else:  # SELL, STRONG_SELL
            stop_loss = round(close + 1.5 * atr, 2)
            target_price = round(close - target_mult * atr, 2)

    return {
        "symbol": signals["symbol"],
        "verdict": verdict,
        "raw_score": round(raw_score, 3),
        "conviction": round(conviction, 3),
        "stop_loss": stop_loss,
        "target_price": target_price,
        "latest_close": close,
        "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
        "scores": {k: (round(v, 3) if v is not None else None) for k, v in scores.items()},
        "weights_used": {k: round(v, 3) for k, v in weights_used.items()},
        "reasoning": reasoning,
        "risk_flags": hard_flags,
    }


# ---------------------------------------------------------------------------
# 3. Persist decision
# ---------------------------------------------------------------------------

def save_decision(decision: dict, stock_id: int) -> None:
    import json
    signals_used = {
        "raw_score": decision["raw_score"],
        "conviction": decision["conviction"],
        "latest_close": decision["latest_close"],
        "atr_pct": decision["atr_pct"],
        "scores": decision["scores"],
        "weights_used": decision["weights_used"],
        "risk_flags": decision["risk_flags"],
    }
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO agent_decisions
                (stock_id, verdict, reasoning, stop_loss, target_price, signals_used, decided_at)
            VALUES
                (:sid, :verdict, :reasoning, :stop_loss, :target_price, :signals_used, NOW())
        """), {
            "sid": stock_id,
            "verdict": decision["verdict"],
            "reasoning": " | ".join(decision["reasoning"]),
            "stop_loss": decision["stop_loss"],
            "target_price": decision["target_price"],
            "signals_used": json.dumps(signals_used),
        })
        conn.commit()


# ---------------------------------------------------------------------------
# 4. CrewAI tool wrapper
# ---------------------------------------------------------------------------

@tool("Decision Analysis Tool")
def decision_tool(symbol: str) -> str:
    """
    Combines Technical, Fundamental, Sentiment, and Prediction signals for a
    stock using a hard-coded risk-rule engine, computes an ATR-based
    stop-loss/target-price, saves the decision, and returns a structured
    summary for the agent to reason over and explain in natural language.
    """
    signals = fetch_latest_signals(symbol)
    decision = apply_risk_rules(signals)
    save_decision(decision, signals["stock_id"])

    lines = [
        f"Symbol: {decision['symbol']}",
        f"Verdict: {decision['verdict']} (conviction: {decision['conviction']})",
        f"Raw weighted score: {decision['raw_score']} (-1 bearish to +1 bullish)",
        f"Latest close: {decision['latest_close']}",
    ]
    if decision["stop_loss"] is not None:
        lines.append(f"Stop-loss: {decision['stop_loss']}  |  Target price: {decision['target_price']}")
    lines.append("Signal scores: " + ", ".join(f"{k}={v}" for k, v in decision["scores"].items()))
    lines.append("Reasoning trail:")
    lines += [f"  - {r}" for r in decision["reasoning"]]
    if decision["risk_flags"]:
        lines.append("Risk flags:")
        lines += [f"  - {f}" for f in decision["risk_flags"]]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    test_symbol = sys.argv[1] if len(sys.argv) > 1 else "TCS"
    result = fetch_latest_signals(test_symbol)
    decision = apply_risk_rules(result)
    save_decision(decision, result["stock_id"])
    print(decision)