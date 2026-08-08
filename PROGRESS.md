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
- **Config**: python-dotenv + config.py

## Status: Technical Agent Complete ✅

| Step | Status | Notes |
|---|---|---|
| 1. Project folder + venv | ✅ Done | `C:\Users\Ashok\AVSCODE\Autonomous-AIstock-Agent` |
| 2. Core dependencies | ✅ Done | crewai, yfinance, pandas, ta, psycopg2-binary, python-dotenv, sqlalchemy |
| 3. PostgreSQL setup | ✅ Done | Postgres 17.10 already installed; skipped TimescaleDB for now |
| 4. DB schema | ✅ Done | 7 tables: stocks, price_history, news_items, sentiment_scores, technical_indicators, predictions, agent_decisions |
| 5. `.env` + config layer | ✅ Done | DB creds + GEMINI_API_KEY |
| 6. Hello agent (CrewAI wiring test) | ✅ Done | Confirmed working end-to-end with Gemini 2.5 Flash |
| 7. **Technical Agent** | ✅ Done | See below |

### Technical Agent — `agents/technical_agent.py`
- `fetch_price_data(symbol)` — pulls OHLCV via yfinance, tries `.NS` then falls back to `.BO`
- `compute_indicators(df)` — SMA-20, EMA-20, RSI-14, MACD (+ signal line), Bollinger Bands, ATR
- `get_latest_signal(df)` — returns latest values + simple bullish/bearish/neutral read
- `get_or_create_stock(symbol)` / `save_indicators(stock_id, df)` — upserts into Postgres (`stocks`, `technical_indicators`) via SQLAlchemy, `ON CONFLICT` on (stock_id, timestamp)
- `technical_analysis_tool` — the above wrapped as a CrewAI `@tool`
- Tested via `test_technical_agent_crew.py`: a real CrewAI Agent + Task + Crew calls the tool and reasons over the output. Verified on TCS and RELIANCE — agent correctly read RSI/MACD/SMA/EMA and produced coherent bullish/bearish assessments.
- Run as a module from project root: `python -m agents.technical_agent` (needed for the `config` import to resolve; `agents/__init__.py` added)

## Next Up
- **News Agent** — pull headlines (Google News RSS / Yahoo Finance RSS / NewsAPI free tier)
- **Sentiment Agent** — FinBERT over News Agent's headlines + StockTwits

## Remaining Build Order
1. ~~Feature store schema~~ ✅
2. ~~Technical Agent~~ ✅
3. News + Sentiment Agents ← **next**
4. Fundamental Agent
5. Prediction Agent + Backtesting
6. Decision Agent with risk rules
7. Orchestrator (scheduling, parallel/sequential agent coordination)
8. Streamlit dashboard + Telegram alerts

## Issues Hit & Resolved
- **Gemini 2.0 Flash quota=0 error**: Google Cloud project had zero free-tier quota (account/billing-level issue, not fixed by regenerating API keys). Resolved by switching to `gemini/gemini-2.5-flash` model instead.
- **Groq + CrewAI bug**: LiteLLM was auto-injecting a `cache_breakpoint` field unsupported by Groq's API, causing every call to fail regardless of model or key. Not a Groq account issue — a library-level incompatibility. Abandoned Groq path in favor of Gemini 2.5 Flash.
- **venv committed to git (247MB)**: `.gitignore` was saved via PowerShell `>` redirect which used the wrong encoding, so git silently ignored the rules. Fixed by rewriting `.gitignore` with `Set-Content -Encoding utf8`, then fully resetting git history (`Remove-Item -Recurse -Force .git` → `git init`) before recommitting.
- **`ModuleNotFoundError: No module named 'config'`**: caused by running the script directly from inside `agents/` instead of as a module from the project root. Fixed by adding `agents/__init__.py` and running `python -m agents.technical_agent`.

## Notes
- Not investment advice — portfolio/learning project.
- yfinance already validated via the earlier [stock-price-mcp-server](https://github.com/Ashok1921/stock-price-mcp-server) project (get_price/get_history/compare_stocks tools).
