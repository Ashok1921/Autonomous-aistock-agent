"""
Orchestrator
------------
Runs the full pipeline for one or more stocks:
    Technical -> News -> Sentiment -> Fundamental -> Prediction -> Decision

The first 5 stages call each agent's plain functions directly (no LLM) --
they don't need reasoning, just fetch+save. Only the Decision stage's
natural-language explanation (via the CrewAI crew in test_decision_agent_crew.py)
costs an LLM call, and it only runs for non-HOLD verdicts by default, to avoid
burning API quota explaining "no data available" HOLDs on every run.

Each stage is wrapped in try/except so one failing stage (e.g. yfinance hiccup,
no headlines yet) doesn't kill the rest of the pipeline for that stock, and one
failing stock doesn't stop the rest of the watchlist.

Run as: python -m agents.orchestrator [SYMBOL ...]
(defaults to TCS RELIANCE INFY HDFCBANK ITC if no symbols given)
"""

import sys

from agents.technical_agent import (
    fetch_price_data, compute_indicators, save_indicators, get_or_create_stock,
)
from agents.news_agent import fetch_news, save_news
from agents.sentiment_agent import get_recent_headlines, score_headlines, save_sentiment, get_stock_id
from agents.fundamental_agent import fetch_fundamentals, save_fundamentals
from agents.prediction_agent import train_and_predict, save_prediction
from agents.decision_agent import fetch_latest_signals, apply_risk_rules, save_decision
from agents.telegram_alerts import send_telegram_alert

# ---------------------------------------------------------------------------
# Individual stage runners -- plain function calls, no LLM
# ---------------------------------------------------------------------------

def run_technical(symbol: str):
    df = fetch_price_data(symbol)
    df = compute_indicators(df)
    stock_id = get_or_create_stock(symbol)
    save_indicators(stock_id, df)
    return stock_id


def run_news(symbol: str, company_name: str = None):
    stock_id = get_or_create_stock(symbol)
    articles = fetch_news(symbol, company_name=company_name)
    save_news(stock_id, articles)
    return len(articles)


def run_sentiment(symbol: str):
    stock_id = get_stock_id(symbol)
    headlines = get_recent_headlines(stock_id)
    if not headlines:
        return None  # nothing to score yet -- not an error, just no data
    results = score_headlines(headlines)
    avg_score = sum(r["score"] for r in results) / len(results)
    avg_confidence = sum(r["confidence"] for r in results) / len(results)
    save_sentiment(stock_id, avg_score, avg_confidence, source="news")
    return avg_score


def run_fundamental(symbol: str):
    stock_id = get_or_create_stock(symbol)
    data = fetch_fundamentals(symbol)
    save_fundamentals(stock_id, data)
    return data


def run_prediction(symbol: str):
    stock_id = get_or_create_stock(symbol)
    prediction = train_and_predict(symbol)
    save_prediction(stock_id, prediction)
    return prediction


def run_decision(symbol: str) -> dict:
    signals = fetch_latest_signals(symbol)
    decision = apply_risk_rules(signals)
    save_decision(decision, signals["stock_id"])
    return decision


# ---------------------------------------------------------------------------
# Per-stock pipeline
# ---------------------------------------------------------------------------

def run_pipeline_for_stock(symbol: str, company_name: str = None) -> dict:
    print(f"\n=== {symbol} ===")
    errors = []

    stages = [
        ("Technical", lambda: run_technical(symbol)),
        ("News", lambda: run_news(symbol, company_name)),
        ("Sentiment", lambda: run_sentiment(symbol)),
        ("Fundamental", lambda: run_fundamental(symbol)),
        ("Prediction", lambda: run_prediction(symbol)),
    ]
    for stage_name, stage_fn in stages:
        try:
            stage_fn()
            print(f"  [OK]   {stage_name}")
        except Exception as e:
            print(f"  [FAIL] {stage_name}: {e}")
            errors.append((stage_name, str(e)))

    decision = None
    try:
        decision = run_decision(symbol)
        print(f"  [OK]   Decision: {decision['verdict']} (conviction {decision['conviction']})")
    except Exception as e:
        print(f"  [FAIL] Decision: {e}")
        errors.append(("Decision", str(e)))
        
    if decision:
        send_telegram_alert(symbol, decision)

    return {"symbol": symbol, "decision": decision, "errors": errors}


# ---------------------------------------------------------------------------
# Watchlist runner
# ---------------------------------------------------------------------------

def run_watchlist(symbols: list[str], company_names: dict = None, explain_non_hold: bool = True) -> list[dict]:
    company_names = company_names or {}
    results = [run_pipeline_for_stock(sym, company_names.get(sym)) for sym in symbols]

    if explain_non_hold:
        from agents.test_decision_agent_crew import crew  # imported lazily -- only needed if we're explaining
        for result in results:
            decision = result["decision"]
            if decision and decision["verdict"] != "HOLD":
                print(f"\n--- Explaining {result['symbol']} ({decision['verdict']}) ---")
                try:
                    output = crew.kickoff(inputs={"symbol": result["symbol"]})
                    print(output)
                except Exception as e:
                    print(f"  [FAIL] Explanation for {result['symbol']}: {e}")

    print("\n=== Summary ===")
    for result in results:
        d = result["decision"]
        verdict = d["verdict"] if d else "FAILED"
        err_note = f" ({len(result['errors'])} stage error(s))" if result["errors"] else ""
        print(f"  {result['symbol']}: {verdict}{err_note}")

    return results


if __name__ == "__main__":
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["TCS", "RELIANCE", "INFY", "HDFCBANK", "ITC"]
    run_watchlist(symbols)