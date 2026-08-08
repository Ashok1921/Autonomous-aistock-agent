
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
- **Config**: python-dotenv + config.py

## Status: Scaffolding Complete ✅

| Step                                | Status  | Notes                                                                                                             |
| ----------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------- |
| 1. Project folder + venv            | ✅ Done | `C:\Users\Ashok\AVSCODE\Autonomous-AIstock-Agent`                                                               |
| 2. Core dependencies                | ✅ Done | crewai, yfinance, pandas, ta, psycopg2-binary, python-dotenv, sqlalchemy                                          |
| 3. PostgreSQL setup                 | ✅ Done | Postgres 17.10 already installed; skipped TimescaleDB for now (plain Postgres is fine at this scale)              |
| 4. DB schema                        | ✅ Done | 7 tables: stocks, price_history, news_items, sentiment_scores, technical_indicators, predictions, agent_decisions |
| 5.`.env` + config layer           | ✅ Done | DB creds + GEMINI_API_KEY                                                                                         |
| 6. Hello agent (CrewAI wiring test) | ✅ Done | Confirmed working end-to-end with Gemini 2.5 Flash                                                                |

## Next Up

- **Technical Agent** — pull OHLCV via yfinance, compute SMA/EMA/RSI/MACD, write to `technical_indicators` table

## Remaining Build Order

1. ~~Feature store schema~~ ✅
2. Technical Agent ← **next**
3. News + Sentiment Agents
4. Fundamental Agent
5. Prediction Agent + Backtesting
6. Decision Agent with risk rules
7. Orchestrator (scheduling, parallel/sequential agent coordination)
8. Streamlit dashboard + Telegram alerts

## Issues Hit & Resolved

- **Gemini 2.0 Flash quota=0 error**: Google Cloud project had zero free-tier quota (account/billing-level issue, not fixed by regenerating API keys). Resolved by switching to `gemini/gemini-2.5-flash` model instead.
- **Groq + CrewAI bug**: LiteLLM was auto-injecting a `cache_breakpoint` field unsupported by Groq's API, causing every call to fail regardless of model or key. Not a Groq account issue — a library-level incompatibility. Abandoned Groq path in favor of Gemini 2.5 Flash.
- **venv committed to git (247MB)**: `.gitignore` was saved via PowerShell `>` redirect which used the wrong encoding, so git silently ignored the rules. Fixed by rewriting `.gitignore` with `Set-Content -Encoding utf8`, then fully resetting git history (`Remove-Item -Recurse -Force .git` → `git init`) before recommitting.

## Notes

- Not investment advice — portfolio/learning project.
- yfinance already validated via the earlier [stock-price-mcp-server](https://github.com/Ashok1921/stock-price-mcp-server) project (get_price/get_history/compare_stocks tools).
