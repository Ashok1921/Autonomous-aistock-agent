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
- **Config**: python-dotenv + config.py

## Status: News + Sentiment Agents Complete ✅

| Step | Status | Notes |
|---|---|---|
| 1. Project folder + venv | ✅ Done | `C:\Users\Ashok\AVSCODE\Autonomous-AIstock-Agent` |
| 2. Core dependencies | ✅ Done | crewai, yfinance, pandas, ta, psycopg2-binary, python-dotenv, sqlalchemy |
| 3. PostgreSQL setup | ✅ Done | Postgres 17.10 already installed; skipped TimescaleDB for now |
| 4. DB schema | ✅ Done | 7 tables: stocks, price_history, news_items, sentiment_scores, technical_indicators, predictions, agent_decisions |
| 5. `.env` + config layer | ✅ Done | DB creds + GEMINI_API_KEY |
| 6. Hello agent (CrewAI wiring test) | ✅ Done | Confirmed working end-to-end with Gemini 2.5 Flash |
| 7. **Technical Agent** | ✅ Done | See below |
| 8. **News Agent** | ✅ Done | See below |
| 9. **Sentiment Agent** | ✅ Done | See below |

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

## Next Up
- **Fundamental Agent** — P/E, P/B, EPS growth, debt/equity, ROE via yfinance `.info`

## Remaining Build Order
1. ~~Feature store schema~~ ✅
2. ~~Technical Agent~~ ✅
3. ~~News + Sentiment Agents~~ ✅
4. Fundamental Agent ← **next**
5. Prediction Agent + Backtesting
6. Decision Agent with risk rules
7. Orchestrator (scheduling, parallel/sequential agent coordination)
8. Streamlit dashboard + Telegram alerts

## Issues Hit & Resolved
- **Gemini 2.0 Flash quota=0 error**: Google Cloud project had zero free-tier quota (account/billing-level issue, not fixed by regenerating API keys). Resolved by switching to `gemini/gemini-2.5-flash` model instead.
- **Groq + CrewAI bug**: LiteLLM was auto-injecting a `cache_breakpoint` field unsupported by Groq's API, causing every call to fail regardless of model or key. Not a Groq account issue — a library-level incompatibility. Abandoned Groq path in favor of Gemini 2.5 Flash.
- **venv committed to git (247MB)**: `.gitignore` was saved via PowerShell `>` redirect which used the wrong encoding, so git silently ignored the rules. Fixed by rewriting `.gitignore` with `Set-Content -Encoding utf8`, then fully resetting git history (`Remove-Item -Recurse -Force .git` → `git init`) before recommitting.
- **`ModuleNotFoundError: No module named 'config'`**: caused by running scripts directly from inside `agents/` instead of as a module from the project root. Fixed by adding `agents/__init__.py` and running with `python -m agents.<module_name>`.

## Notes
- Not investment advice — portfolio/learning project.
- yfinance already validated via the earlier [stock-price-mcp-server](https://github.com/Ashok1921/stock-price-mcp-server) project (get_price/get_history/compare_stocks tools).
