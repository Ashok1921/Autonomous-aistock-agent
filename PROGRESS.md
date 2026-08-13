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
- **Dashboard**: Streamlit
- **Alerts**: Telegram Bot API (raw HTTP via `requests`)
- **Config**: python-dotenv + config.py

## Status: Project Complete ✅ (v1)

| Step                                        | Status  | Notes                                                                                                             |
| ------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------- |
| 1. Project folder + venv                    | ✅ Done | `C:\Users\Ashok\AVSCODE\Autonomous-AIstock-Agent`                                                               |
| 2. Core dependencies                        | ✅ Done | crewai, yfinance, pandas, ta, psycopg2-binary, python-dotenv, sqlalchemy, scikit-learn, streamlit, requests       |
| 3. PostgreSQL setup                         | ✅ Done | Postgres 17.10 already installed; skipped TimescaleDB for now                                                     |
| 4. DB schema                                | ✅ Done | 7 tables: stocks, price_history, news_items, sentiment_scores, technical_indicators, predictions, agent_decisions |
| 5.`.env` + config layer                   | ✅ Done | DB creds + GEMINI_API_KEY + TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID                                                 |
| 6. Hello agent (CrewAI wiring test)         | ✅ Done | Confirmed working end-to-end with Gemini 2.5 Flash                                                                |
| 7.**Technical Agent**                 | ✅ Done | See below                                                                                                         |
| 8.**News Agent**                      | ✅ Done | See below                                                                                                         |
| 9.**Sentiment Agent**                 | ✅ Done | See below                                                                                                         |
| 10.**Fundamental Agent**              | ✅ Done | See below                                                                                                         |
| 11.**Prediction + Backtesting Agent** | ✅ Done | See below                                                                                                         |
| 12.**Decision Agent**                 | ✅ Done | See below                                                                                                         |
| 13.**Orchestrator**                   | ✅ Done | See below                                                                                                         |
| 14.**Streamlit Dashboard**            | ✅ Done | See below                                                                                                         |
| 15.**Telegram Alerts**                | ✅ Done | See below                                                                                                         |

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
- **dividend_yield bug**: yfinance's `dividendYield` is already a percent, never a fraction needing ×100. Diagnosed across 5 tickers (TCS/RELIANCE/INFY/HDFCBANK/ITC), fixed to use the raw value directly. Verified correct across all 5 (2.65/0.45/4.25/1.78/5.59)
- **Known limitation**: `roe`/`roa`/`current_ratio`/`free_cashflow` come back `None` for some tickers — a yfinance data-availability gap, not a bug (later confirmed again on RELIANCE via the dashboard's Fundamentals tab)
- Tested via `test_fundamental_agent_crew.py` on RELIANCE — agent correctly reasoned over P/E, PEG, debt-to-equity, revenue growth and gave a coherent "Strong" verdict
- Run as a module from project root: `python -m agents.fundamental_agent`

### Prediction Agent — `agents/prediction_agent.py`

- Random Forest Regressor trained on technical indicators (SMA/EMA/RSI/MACD/Bollinger/ATR) + return/volume features pulled fresh from yfinance
- Predicts next-day % change, derives direction (up/down/flat), saves to `predictions` (predicted_direction, predicted_change_pct, confidence, horizon, target_date)
- Fixed an `inf`-value bug from zero-volume days breaking sklearn (replaced with `NaN` before training)
- Confidence metric swapped from R² (uninformative, always ~0) to directional accuracy via `TimeSeriesSplit` cross-validation
- **Backtesting harness** (`backtest_prediction_agent.py`): walk-forward test, retrains every 5 days across 2 years for 5 stocks, 280 total predictions. **Result: overall directional accuracy exactly 0.500 (coin flip)**, mean abs error 1.037%; per-stock ranged 0.429 (INFY) to 0.589 (TCS)
- **Conclusion**: a Random Forest trained on technical indicators alone has no meaningful predictive edge on next-day price direction for these stocks — consistent with market-efficiency expectations for short-horizon technical-only prediction. Documented as an honest finding rather than tuned away
- Tested via `test_prediction_agent_crew.py` with explicit honesty instructions (confidence <0.55 = "little to no real predictive edge") — agent correctly refused to oversell the weak result
- Implication for the Decision Agent: Prediction Agent output weighted low/skeptically relative to Fundamental and Sentiment signals — confirmed in production during real BUY-verdict testing, where a 0.5-confidence prediction was correctly scored near zero
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
  - Produces verdict: `STRONG_BUY` / `BUY` / `HOLD` / `SELL` / `STRONG_SELL`, plus an ATR-based `stop_loss`/`target_price` (only set for non-HOLD verdicts — intentional, not a gap)
  - **BUY/SELL conviction threshold: 0.4** (STRONG_BUY/STRONG_SELL: 0.6) — confirmed as the correct permanent value after a controlled test at 0.3 (see Telegram Alerts section below); reverted back to 0.4
- `save_decision(decision, stock_id)` — persists to `agent_decisions` (`verdict`, `reasoning`, `stop_loss`, `target_price`, `signals_used` as `jsonb` containing the full per-signal score/weight/risk-flag trail)
- `decision_tool` — wrapped as a CrewAI `@tool` ("Decision Analysis Tool")
- **Real schema differences from initial assumptions**: `technical_indicators` uses `rsi_14`/`timestamp` and has no close price column; `fundamentals` uses `fetched_at`; `sentiment_scores` uses `score`/`confidence`/`computed_at`; `agent_decisions` uses `verdict`/`reasoning`/`stop_loss`/`target_price`/`signals_used` (jsonb), not a `conviction`/`raw_score` column pair as first assumed — queries and inserts rewritten to match the real schema
- **`price_history` was empty** — added `agents/backfill_price_history.py` (yfinance, `.NS`/`.BO` fallback, dedup on `stock_id`+`timestamp`) and backfilled 125 rows each for TCS, RELIANCE, INFY, HDFCBANK, ITC
- **Bug fixed — Decimal/float mismatch**: Postgres `numeric` columns come back as `decimal.Decimal` via SQLAlchemy, which doesn't mix with `float` arithmetic in the scoring functions. Fixed with a `_row_to_float_dict()` helper that casts every numeric field to `float` right after fetching
- Verified end-to-end on all 5 stocks:
  - **RELIANCE** → `BUY`, conviction 0.417, stop-loss 1277.52 / target 1348.48, correctly flagged missing critical fundamentals as capping conviction
  - **TCS** → `HOLD`, conviction 0.341 (below the 0.4 threshold needed for a BUY call)
  - **INFY / HDFCBANK / ITC** → `HOLD` with a "no usable signals at all" flag, since those three stocks hadn't been run through the upstream agents yet at that point (a data-coverage gap, not a Decision Agent bug — later resolved once run through the full Orchestrator)
- Tested via `test_decision_agent_crew.py`: a real CrewAI Agent + Task + Crew explains the decision in plain English without ever overriding the verdict, conviction, stop-loss, or target-price. Explicit instructions require it to state risk flags and stale/missing data plainly rather than soften them. Verified on RELIANCE — agent correctly named technical + fundamentals as the drivers, stated the missing-fundamentals risk flag directly, and reported conviction/stop-loss/target accurately
- Run as a module from project root: `python -m agents.decision_agent [SYMBOL]` (defaults to TCS), `python -m agents.test_decision_agent_crew [SYMBOL]` (defaults to RELIANCE)

### Orchestrator — `agents/orchestrator.py`

- Runs the full pipeline for one or more stocks: Technical → News → Sentiment → Fundamental → Prediction → Decision
- The first 5 stages call each agent's plain functions directly (no LLM) — pure fetch/save operations, no reasoning needed:
  - `run_technical`, `run_news`, `run_sentiment`, `run_fundamental`, `run_prediction`, `run_decision`
- Each stage wrapped in try/except so one failing stage doesn't kill the rest of the pipeline for that stock, and one failing stock doesn't stop the rest of the watchlist
- **Cost-aware design**: the Decision Agent's LLM explanation crew only runs for non-HOLD verdicts (`explain_non_hold=True` by default), imported lazily inside `run_watchlist()` so it's not even loaded unless needed — avoids burning Gemini free-tier quota explaining routine HOLD calls
- Exposes `run_pipeline_for_stock(symbol, company_name=None) -> dict` ({"symbol", "decision", "errors"}) — used directly by the dashboard's "Run Pipeline Now" button — and `run_watchlist(symbols, company_names=None, explain_non_hold=True)` for the full batch run
- Now also fires a Telegram alert (see below) right after the decision is saved
- Verified end-to-end on all 5 stocks (TCS, RELIANCE, INFY, HDFCBANK, ITC) multiple times, including a run where RELIANCE correctly produced a real BUY verdict and triggered both the Telegram alert and the CrewAI explanation
- Run as a module from project root: `python -m agents.orchestrator [SYMBOL ...]` (defaults to TCS RELIANCE INFY HDFCBANK ITC if no symbols given)

### Streamlit Dashboard — `dashboard.py`

- Sidebar: stock picker (5-stock watchlist) + "Run Pipeline Now" button — calls `orchestrator.run_pipeline_for_stock(symbol)` live (not just reading stale DB data)
- Watchlist overview: color-coded verdict cards (green=BUY, red=SELL, gray=HOLD) with stop-loss/target per stock
- Per-stock drill-down: price history chart + tabs for Technical / Fundamentals / Sentiment / Prediction / Decision Reasoning, each reading the latest row from its respective table
- **Bugs fixed during build**:
  - `config.py` only exposes `DATABASE_URL`, not an `engine` object — dashboard builds its own via `create_engine(DATABASE_URL)`
  - `agent_decisions` has no `created_at` column (query originally assumed one) — removed from the overview query
  - Streamlit wasn't installed in the project venv, and Windows PATH resolved `streamlit` to a different global install — fixed via `pip install streamlit` inside the activated venv + running as `python -m streamlit run dashboard.py`
  - `₹nan` displayed for HOLD stocks' stop-loss/target: Postgres `NULL` becomes pandas `NaN` (a float), which is *truthy* in Python — `if row['stop_loss']` let `NaN` through. Fixed by switching to `pd.notna()` checks — kept permanently
- Verified end-to-end: ran live pipeline for all 5 stocks via the dashboard button, watchlist overview and all 5 detail tabs populated correctly; cross-checked every tab's values against raw `signals_used` JSON in the DB for RELIANCE — exact match across every field
- Run as: `streamlit run dashboard.py` (with venv activated) or `python -m streamlit run dashboard.py`

### Telegram Alerts — `agents/telegram_alerts.py`

- `send_telegram_alert(symbol, decision)` — sends a formatted message via the raw Telegram Bot API (`requests`, no SDK) whenever a non-HOLD verdict is produced; silently no-ops on HOLD
- Reads `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` from `.env`; fails gracefully (prints a warning, never raises) if credentials are missing or the request fails, so a Telegram outage can't take down the pipeline
- Message includes: verdict + emoji, conviction score, stop-loss, target price, and the reasoning trail
- Wired into `agents/orchestrator.py`'s `run_pipeline_for_stock()`, firing right after the decision is saved
- Bot created via @BotFather (`ashok_stock_agent` / t.me/ashok_stock_agent_bot)
- **Verified twice**:
  1. Standalone `test_telegram_alert.py` with a fake BUY decision confirmed message formatting and delivery worked
  2. **Full real-data verification**: temporarily lowered the BUY/SELL conviction threshold in `decision_agent.py` from 0.4 to 0.3 to let RELIANCE's real conviction (0.364) legitimately cross into BUY, then ran `python -m agents.orchestrator RELIANCE` — confirmed the alert fired automatically from inside the live pipeline (not just the test script), alongside a correct, honest CrewAI explanation citing the missing-fundamentals risk flag. Threshold reverted back to 0.4 immediately after this test — 0.4 remains the permanent value

## Verification Summary

- All 6 core agents individually tested with real data (TCS/RELIANCE/INFY/HDFCBANK/ITC) and wrapped in CrewAI Agent+Task+Crew tests
- Full orchestrator run verified end-to-end across all 5 watchlist stocks, multiple times
- Dashboard cross-checked tab-by-tab against raw DB values for RELIANCE — exact match
- Telegram alert chain (signals → decision → DB save → alert → Telegram) verified via a real, non-mocked pipeline run that crossed the BUY threshold
- Confirmed HOLD verdicts correctly leave `stop_loss`/`target_price` as `NULL` by design — not a bug
- Root-caused RELIANCE's moderate conviction (0.335–0.364) to two real, expected factors: missing ROE/ROA/current_ratio/free_cashflow fundamentals data (yfinance limitation) and a low-confidence (0.5, coinflip) Prediction Agent signal correctly discounted by the Decision Agent's weighting

## Remaining Build Order

1. ~~Feature store schema~~ ✅
2. ~~Technical Agent~~ ✅
3. ~~News + Sentiment Agents~~ ✅
4. ~~Fundamental Agent~~ ✅
5. ~~Prediction Agent + Backtesting~~ ✅
6. ~~Decision Agent with risk rules~~ ✅
7. ~~Orchestrator~~ ✅
8. ~~Streamlit dashboard~~ ✅
9. ~~Telegram alerts~~ ✅

**All planned build steps complete.**

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
- **Dashboard `config import engine` ImportError**: `config.py` only ever exposed `DATABASE_URL`, not an `engine` object — every agent built its own engine locally. Fixed by doing the same in `dashboard.py`.
- **`streamlit` not found / wrong Python used**: Windows PATH resolved the global Python's `streamlit.exe` instead of the venv's, even with the venv activated. Fixed by installing streamlit into the venv and invoking it as `python -m streamlit run dashboard.py`.
- **`₹nan` shown for HOLD stocks in the dashboard**: Postgres `NULL` → pandas `NaN`, which is truthy in Python, so `if row['stop_loss']` let it through to the currency formatter. Fixed with `pd.notna()` checks.

## Possible Future Work (not started)

- Expand watchlist beyond the current 5 stocks
- Scheduled/recurring runs (cron or APScheduler) instead of manual dashboard trigger
- Alternative fundamentals data source to close the ROE/ROA/current_ratio gap

## Notes

- Not investment advice — portfolio/learning project.
- yfinance already validated via the earlier [stock-price-mcp-server](https://github.com/Ashok1921/stock-price-mcp-server) project (get_price/get_history/compare_stocks tools

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
| 13.**Orchestrator**                   | ✅ Done | See                                         below                                                                 |

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

## Status: Orchestrator Complete ✅

### Orchestrator — `agents/orchestrator.py`

- Runs the full pipeline for one or more stocks: Technical → News → Sentiment → Fundamental → Prediction → Decision
- The first 5 stages call each agent's plain functions directly (no LLM) — they're pure fetch/save operations and don't need reasoning:
  - `run_technical`, `run_news`, `run_sentiment`, `run_fundamental`, `run_prediction`, `run_decision`
- Each stage wrapped in try/except so one failing stage doesn't kill the rest of the pipeline for that stock, and one failing stock doesn't stop the rest of the watchlist
- **Cost-aware design**: the Decision Agent's LLM explanation (`test_decision_agent_crew.py`'s `crew`) only runs for non-HOLD verdicts (`explain_non_hold=True` by default), imported lazily inside `run_watchlist()` so it's not even loaded unless needed — avoids burning Gemini free-tier quota explaining routine HOLD calls on every scheduled run
- `run_watchlist(symbols, company_names=None, explain_non_hold=True)` — main entry point, loops over a list of symbols and prints a per-stock summary at the end
- Verified end-to-end on all 5 stocks (TCS, RELIANCE, INFY, HDFCBANK, ITC): all 5 stages succeeded for every stock, Decision computed for all 5 (all landed on HOLD on this particular run — a legitimate outcome, not a bug). INFY/HDFCBANK/ITC — which previously had no data in Technical/Fundamental/Sentiment/Prediction tables — now have real signals feeding into their Decision output
- The non-HOLD explanation path (lazy import of `test_decision_agent_crew`) wasn't exercised by that run since everything was HOLD; verified separately by calling `crew.kickoff()` directly for RELIANCE — confirmed working, correctly explained a HOLD verdict including the missing-fundamentals risk flag
- Run as a module from project root: `python -m agents.orchestrator [SYMBOL ...]` (defaults to TCS RELIANCE INFY HDFCBANK ITC if no symbols given)

## Next Up

- **Streamlit dashboard + Telegram alerts** — surface the pipeline's output (verdicts, conviction, stop-loss/target, explanations) somewhere visible instead of terminal output only

## Remaining Build Order

1. ~~Feature store schema~~ ✅
2. ~~Technical Agent~~ ✅
3. ~~News + Sentiment Agents~~ ✅
4. ~~Fundamental Agent~~ ✅
5. ~~Prediction Agent + Backtesting~~ ✅
6. ~~Decision Agent with risk rules~~ ✅
7. ~~Orchestrator~~ ✅
8. Streamlit dashboard + Telegram alerts ← **next**

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
