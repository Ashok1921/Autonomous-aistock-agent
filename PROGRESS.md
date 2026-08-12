
# Autonomous AI Stock Market Agent — Progress Log

## Overview

Multi-agent AI system for Indian stock market (NSE/BSE) analysis using CrewAI.
Agents: Technical, Fundamental, News, Sentiment, Prediction, Decision, Orchestrator.
Constraint: 100% free — no paid APIs, no paid deployments, runs locally.

Follow-up project to [stock-price-mcp-server](https://github.com/Ashok1921/stock-price-mcp-server).

## Tech Stack

- **Agent framework**: CrewAI
- **LLM**: Google Gemini 2.5 Flash (free tier)
- **Database**: PostgreSQL 17.10 (local, no TimescaleDB for now)
- **Data source**: yfinance (NSE/BSE via .NS/.BO suffixes)
- **Indicators**: `ta` library (SMA, EMA, RSI, MACD, Bollinger Bands, ATR)
- **News**: Google News RSS via `feedparser` (no API key needed)
- **Sentiment**: FinBERT (`ProsusAI/finbert` via `transformers` + `torch`)
- **Prediction**: scikit-learn RandomForestRegressor, time-series cross-validation
- **Config**: python-dotenv + config.py

## Status: Decision Agent Complete ✅

| Step                                        | Status  | Notes                                                                                                             |
| ------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------- |
| 1. Project folder + venv                    | ✅ Done | `C:\Users\Ashok\AVSCODE\Autonomous-AIstock-Agent`                                                               |
| 2. Core dependencies                        | ✅ Done | crewai, yfinance, pandas, ta, psycopg2-binary, python-dotenv, sqlalchemy, scikit-learn                            |
| 3. PostgreSQL setup                         | ✅ Done | Postgres 17.10 already installed; skipped TimescaleDB for now                                                     |
| 4. DB schema                                | ✅ Done | 7 tables: stocks, price_history, news_items, sentiment_scores, technical_indicators, predictions, agent_decisions |
| 5.`.env` + config layer                   | ✅ Done | DB creds + GEMINI_API_KEY                                                                                         |
| 6. Hello agent (CrewAI wiring test)         | ✅ Done | Confirmed working end-to-end with Gemini 2.5 Flash                                                                |
| 7.**Technical Agent**                 | ✅ Done | See below                                                                                                         |
| 8.**News Agent**                      | ✅ Done | See below                                                                                                         |
| 9.**Sentiment Agent**                 | ✅ Done | See below                                                                                                         |
| 10.**Fundamental Agent**              | ✅ Done | See below                                                                                                         |
| 11.**Prediction + Backtesting Agent** | ✅ Done | See below                                                                                                         |
| 12.**Decision Agent**                 | ✅ Done | See below                                                                                                         |

### Technical Agent — `agents/technical_agent.py`

- `fetch_price_data(symbol)` — pulls OHLCV via yfinance, tries `.NS` then falls back to `.BO`
- `compute_indicators(df)` — SMA-20, EMA-20, RSI-14, MACD (+ signal line), Bollinger Bands, ATR
- `get_latest_signal(df)` — returns latest values + simple bullish/bearish/neutral read
- `get_or_create_stock(symbol)` / `save_indicators(stock_id, df)` — upserts into Postgres (`stocks`, `technical_indicators`) via SQLAlchemy, `ON CONFLICT` on (stock_id, timestamp)
- `technical_analysis_tool` — the above wrapped as a CrewAI `@tool`
- Tested via `test_technical_agent_crew.py`: a real CrewAI Agent + Task + Crew calls the tool and reasons over the output. Verified on TCS and RELIANCE.
- Run as a module from project root: `python -m agents.technical_agent`

### News Agent — `agents/news_agent.py`

- `fetch_news(symbol, company_name)` — pulls recent headlines from Google News RSS (`feedparser`), no API key needed
- `save_news(stock_id, articles)` — persists into `news_items`, deduped by URL, publish dates parsed via `email.utils.parsedate_to_datetime`
- `news_fetch_tool` — wrapped as a CrewAI `@tool`
- Verified: 10 real TCS headlines fetched and saved cleanly with correct source/date metadata

### Sentiment Agent — `agents/sentiment_agent.py`

- Uses FinBERT (`ProsusAI/finbert`) loaded via `transformers`/`torch` — classifies text as positive/negative/neutral, normalized to a -1 to +1 score
- `score_headline()` / `score_headlines()` — per-headline scoring
- `get_recent_headlines(stock_id)` — pulls latest headlines from `news_items` (real News Agent output, not hardcoded)
- `save_sentiment(stock_id, avg_score, avg_confidence)` — persists aggregate to `sentiment_scores`
- `sentiment_analysis_tool` — wrapped as a CrewAI `@tool`
- Verified end-to-end on 10 real TCS headlines: correctly distinguished strongly positive/negative/neutral headlines, aggregated to overall sentiment (-0.227, negative) with high confidence (0.905)
- Run as a module from project root: `python -m agents.sentiment_agent`

### Fundamental Agent — `agents/fundamental_agent.py`

- New `fundamentals` table added to Postgres via migration `add_fundamentals_table.sql`
- `fetch_fundamentals(symbol)` — pulls P/E, forward P/E, EPS, PEG ratio, debt-to-equity, ROE, ROA, market cap, dividend yield, book value, price-to-book, revenue growth, profit margin, current ratio, free cash flow via yfinance `.info`, tries `.NS` then falls back to `.BO`
- `save_fundamentals(stock_id, data)` — upserts into `fundamentals` via SQLAlchemy `engine` + `text()`, same style as `technical_agent.py`, `ON CONFLICT` on (stock_id, fetched_at); reuses `get_or_create_stock()` from the Technical Agent
- `fundamental_analysis_tool` — wrapped as a CrewAI `@tool` ("Fundamental Analysis Tool")
- Tested via `test_fundamental_agent_crew.py`: a real CrewAI Agent + Task + Crew calls the tool and reasons across valuation, profitability, leverage, and growth. Verified on RELIANCE — agent gave a coherent "Strong" verdict backed by real P/E, PEG, debt-to-equity, and revenue growth figures
- **Bug fixed — dividend_yield miscalculation**: yfinance's `dividendYield` field is already a percentage (e.g. `2.65` = 2.65%), never a fraction needing ×100. Root-caused by diagnosing raw `.info` fields across 5 tickers (TCS, RELIANCE, INFY, HDFCBANK, ITC); the original `pct()` heuristic was multiplying some values by 100 incorrectly. Fixed to use `dividendYield` directly; re-verified correct across all 5 tickers (2.65 / 0.45 / 4.25 / 1.78 / 5.59)
- **Known limitation**: `roe`, `roa`, `current_ratio`, `free_cashflow` come back `None` for some tickers — a yfinance data-availability gap, not a bug in our code. Downstream agents (Decision) need to handle these fields possibly being `None`
- Run as a module from project root: `python -m agents.fundamental_agent`

### Prediction + Backtesting Agent — `agents/prediction_agent.py`, `backtest_prediction_agent.py`

- `fetch_training_data(symbol)` — pulls ~2 years of daily OHLCV directly from yfinance (not from `price_history`/`technical_indicators`, which don't store enough raw history yet)
- `build_features(df)` — computes the same technical indicators as the Technical Agent (SMA, EMA, RSI, MACD, Bollinger, ATR) plus 1-day/5-day returns and volume change, with next-day % change as the training target
- `train_and_predict(symbol, horizon)` — trains a `RandomForestRegressor`, predicts tomorrow's % change, derives a direction call (`up`/`down`/`flat`), and computes a confidence score
- `save_prediction(stock_id, prediction)` — writes to the existing `predictions` table (`predicted_direction`, `predicted_change_pct`, `confidence`, `horizon`, `target_date`)
- `prediction_tool` — wrapped as a CrewAI `@tool` ("Prediction Tool")
- **Bug fixed — infinite values**: zero-volume days (holidays/thin trading) caused `pct_change()` on volume to produce `inf`, which crashed `sklearn`. Fixed by replacing `inf`/`-inf` with `NaN` before training.
- **Confidence metric redesigned**: initial R²-based confidence came back `0.0` (R² is a poor fit for noisy daily returns). Replaced with directional accuracy measured via `TimeSeriesSplit` cross-validation — more interpretable (0.5 = coin flip).
- Tested via `test_prediction_agent_crew.py` with explicit honesty instructions in the task prompt: if confidence is below 0.55, the agent must state plainly that the model shows little to no real predictive edge, rather than oversell a weak result. Verified on TCS (confidence 0.463) — agent correctly reported the prediction as not a strong signal instead of dressing it up.
- **Backtested** (`backtest_prediction_agent.py`) with a proper walk-forward methodology: retrains every 5 trading days across ~2 years of history, across 5 stocks (TCS, RELIANCE, INFY, HDFCBANK, ITC), 280 total out-of-sample predictions, no lookahead.
  - **Result: overall directional accuracy = 0.500 (exactly a coin flip)**, mean absolute error = 1.037%.
  - Per-stock accuracy ranged from 0.429 (INFY — worse than random) to 0.589 (TCS), consistent with sampling noise around a true null result rather than genuine per-stock skill.
  - **Conclusion**: a Random Forest trained on technical indicators alone has no meaningful predictive edge on next-day price direction for these stocks — consistent with market-efficiency expectations for short-horizon technical-only prediction. Documented as an honest finding rather than tuned away.
  - Implication for the Decision Agent: Prediction Agent output should be weighted low/skeptically relative to Fundamental and Sentiment signals, which is exactly what the Decision Agent's risk rules do.
- Run as a module from project root: `python -m agents.prediction_agent` (live prediction), `python backtest_prediction_agent.py` (evaluation only, does not write to `predictions` table)

### Decision Agent — `agents/decision_agent.py`

- `fetch_latest_signals(symbol)` — pulls the latest row from `technical_indicators`, `fundamentals`, `sentiment_scores`, `predictions`, and `price_history` (for latest close, needed for ATR% and stop-loss/target-price math) via SQLAlchemy `engine` + `text()`, same style as the other agents; reuses `get_or_create_stock()`
- `apply_risk_rules(signals)` — hard-coded risk-rule engine that combines the four signals into a verdict:
  - Base weights: fundamentals 0.40, technical 0.25, sentiment 0.20, prediction 0.15 — prediction deliberately underweighted given the backtested 0.500 (coin-flip) accuracy
  - Stale data (>48h old) halves that signal's weight
  - Missing critical fundamentals (PE/ROE/D-E) caps conviction at moderate (0.5)
  - Fundamentals vs. sentiment strongly disagreeing dampens conviction
  - High volatility (ATR >4% of latest close) reduces conviction
  - A decision resting almost entirely on the Prediction signal is capped low (0.3), since it has no real standalone edge
  - Produces verdict: `STRONG_BUY` / `BUY` / `HOLD` / `SELL` / `STRONG_SELL`, plus an ATR-based `stop_loss`/`target_price` (only set for non-HOLD verdicts)
- `save_decision(decision, stock_id)` — persists to `agent_decisions` (`verdict`, `reasoning`, `stop_loss`, `target_price`, `signals_used` as `jsonb` containing the full per-signal score/weight/risk-flag trail)
- `decision_tool` — wrapped as a CrewAI `@tool` ("Decision Analysis Tool")
- **Real schema differences from initial assumptions**: `technical_indicators` uses `rsi_14`/`timestamp` and has no close price column; `fundamentals` uses `fetched_at`; `sentiment_scores` uses `score`/`confidence`/`computed_at`; `agent_decisions` uses `verdict`/`reasoning`/`stop_loss`/`target_price`/`signals_used` (jsonb), not a `conviction`/`raw_score` column pair as first assumed — queries and inserts rewritten to match the real schema
- **`price_history` was empty** — added `agents/backfill_price_history.py` (yfinance, `.NS`/`.BO` fallback, dedup on `stock_id`+`timestamp`) and backfilled 125 rows each for TCS, RELIANCE, INFY, HDFCBANK, ITC
- **Bug fixed — Decimal/float mismatch**: Postgres `numeric` columns come back as `decimal.Decimal` via SQLAlchemy, which doesn't mix with `float` arithmetic in the scoring functions. Fixed with a `_row_to_float_dict()` helper that casts every numeric field to `float` right after fetching
- Verified end-to-end on all 5 stocks:
  - **RELIANCE** → `BUY`, conviction 0.417, stop-loss 1277.52 / target 1348.48, correctly flagged missing critical fundamentals as capping conviction
  - **TCS** → `HOLD`, conviction 0.341 (below the 0.4 threshold needed for a BUY call)
  - **INFY / HDFCBANK / ITC** → `HOLD` with a "no usable signals at all" flag, since those three stocks haven't been run through the upstream Technical/Fundamental/Sentiment/Prediction agents yet (a data-coverage gap, not a Decision Agent bug)
- Tested via `test_decision_agent_crew.py`: a real CrewAI Agent + Task + Crew explains the decision in plain English without ever overriding the verdict, conviction, stop-loss, or target-price. Explicit instructions require it to state risk flags and stale/missing data plainly rather than soften them. Verified on RELIANCE — agent correctly named technical + fundamentals as the drivers, stated the missing-fundamentals risk flag directly, and reported conviction/stop-loss/target accurately
- Run as a module from project root: `python -m agents.decision_agent [SYMBOL]` (defaults to TCS), `python -m agents.test_decision_agent_crew [SYMBOL]` (defaults to RELIANCE)

## Next Up

- **Orchestrator** — tie Technical → News → Sentiment → Fundamental → Prediction → Decision into a single automatic run per stock (and eventually per watchlist, on a schedule)

## Remaining Build Order

1. ~~Feature store schema~~ ✅
2. ~~Technical Agent~~ ✅
3. ~~News + Sentiment Agents~~ ✅
4. ~~Fundamental Agent~~ ✅
5. ~~Prediction Agent + Backtesting~~ ✅
6. ~~Decision Agent with risk rules~~ ✅
7. Orchestrator (scheduling, parallel/sequential agent coordination) ← **next**
8. Streamlit dashboard + Telegram alerts

## Issues Hit & Resolved

- **Gemini 2.0 Flash quota=0 error**: Google Cloud project had zero free-tier quota (account/billing-level issue, not fixed by regenerating API keys). Resolved by switching to `gemini/gemini-2.5-flash` model instead.
- **Groq + CrewAI bug**: LiteLLM was auto-injecting a `cache_breakpoint` field unsupported by Groq's API, causing every call to fail regardless of model or key. Not a Groq account issue — a library-level incompatibility. Abandoned Groq path in favor of Gemini 2.5 Flash.
- **venv committed to git (247MB)**: `.gitignore` was saved via PowerShell `>` redirect which used the wrong encoding, so git silently ignored the rules. Fixed by rewriting `.gitignore` with `Set-Content -Encoding utf8`, then fully resetting git history (`Remove-Item -Recurse -Force .git` → `git init`) before recommitting.
- **`ModuleNotFoundError: No module named 'config'`**: caused by running scripts directly from inside `agents/` instead of as a module from the project root. Fixed by adding `agents/__init__.py` and running with `python -m agents.<module_name>`.
- **dividend_yield miscalculated in Fundamental Agent**: yfinance's `dividendYield` is already a percent, not a fraction — see Fundamental Agent section above for the diagnosis and fix.
- **`inf` values crashing sklearn in Prediction Agent**: zero-volume days produced infinite values via `pct_change()` on volume; fixed by replacing `inf`/`-inf` with `NaN` before training.
- **R²-based prediction confidence was uninformative (always ~0)**: replaced with directional accuracy from time-series cross-validation, which is far more interpretable for this problem.
- **Decision Agent queries failed against real schema**: initial `decision_agent.py` was written against assumed column names (`rsi`, `sma_50`, `avg_sentiment`, `close_price`, `conviction`/`raw_score` in `agent_decisions`). Fixed by pulling actual column names via `information_schema.columns` and rewriting every query to match.
- **`decimal.Decimal` breaking float arithmetic in risk scoring**: Postgres `numeric` columns return as `Decimal` via SQLAlchemy; mixing with `float` in the risk-rule scoring functions raised `TypeError`. Fixed with a row-level float-casting helper applied right after fetch.
- **`price_history` table was empty**, blocking ATR%/stop-loss/target-price calculation in the Decision Agent. Fixed with a standalone `backfill_price_history.py` script.

## Notes

- Not investment advice — portfolio/learning project.
- yfinance already validated via the earlier [stock-price-mcp-server](https://github.com/Ashok1921/stock-price-mcp-server) project (get_price/get_history/compare_stocks tools).
