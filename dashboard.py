"""
Streamlit Dashboard
--------------------
Live dashboard for the autonomous stock agent pipeline.

Run as: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

from agents.orchestrator import run_pipeline_for_stock
from sqlalchemy import create_engine
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)



WATCHLIST = ["TCS", "RELIANCE", "INFY", "HDFCBANK", "ITC"]

VERDICT_COLORS = {
    "STRONG_BUY": "#00c853",
    "BUY": "#69f0ae",
    "HOLD": "#9e9e9e",
    "SELL": "#ff8a80",
    "STRONG_SELL": "#d50000",
}

st.set_page_config(page_title="Autonomous Stock Agent", layout="wide")
st.title("📈 Autonomous Stock Market Agent")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Controls")
selected_symbol = st.sidebar.selectbox("Select stock", WATCHLIST)
run_all = st.sidebar.checkbox("Run for all 5 stocks", value=False)

if st.sidebar.button("🚀 Run Pipeline Now"):
    targets = WATCHLIST if run_all else [selected_symbol]
    for sym in targets:
        with st.spinner(f"Running pipeline for {sym}..."):
            result = run_pipeline_for_stock(sym)
        if result["errors"]:
            st.sidebar.warning(f"{sym}: {len(result['errors'])} stage error(s) — {result['errors']}")
        else:
            st.sidebar.success(f"{sym}: pipeline complete")
    st.rerun()

st.sidebar.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")

# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------
def get_latest_decisions():
    query = text("""
        SELECT s.symbol, d.verdict, d.reasoning, d.stop_loss, d.target_price,
               d.signals_used
        FROM agent_decisions d
        JOIN stocks s ON s.id = d.stock_id
        WHERE d.id IN (
            SELECT MAX(id) FROM agent_decisions GROUP BY stock_id
        )
        ORDER BY s.symbol
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def get_price_history(symbol):
    query = text("""
        SELECT p.timestamp, p.close
        FROM price_history p
        JOIN stocks s ON s.id = p.stock_id
        WHERE s.symbol = :symbol
        ORDER BY p.timestamp
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"symbol": symbol})


def get_technical(symbol):
    query = text("""
        SELECT t.*
        FROM technical_indicators t
        JOIN stocks s ON s.id = t.stock_id
        WHERE s.symbol = :symbol
        ORDER BY t.timestamp DESC LIMIT 1
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"symbol": symbol})


def get_fundamentals(symbol):
    query = text("""
        SELECT f.*
        FROM fundamentals f
        JOIN stocks s ON s.id = f.stock_id
        WHERE s.symbol = :symbol
        ORDER BY f.fetched_at DESC LIMIT 1
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"symbol": symbol})


def get_sentiment(symbol):
    query = text("""
        SELECT sc.*
        FROM sentiment_scores sc
        JOIN stocks s ON s.id = sc.stock_id
        WHERE s.symbol = :symbol
        ORDER BY sc.computed_at DESC LIMIT 1
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"symbol": symbol})


def get_prediction(symbol):
    query = text("""
        SELECT pr.*
        FROM predictions pr
        JOIN stocks s ON s.id = pr.stock_id
        WHERE s.symbol = :symbol
        ORDER BY pr.target_date DESC LIMIT 1
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"symbol": symbol})


# ---------------------------------------------------------------------------
# Overview table
# ---------------------------------------------------------------------------
st.subheader("Watchlist Overview")

try:
    decisions_df = get_latest_decisions()
except Exception as e:
    decisions_df = pd.DataFrame()
    st.error(f"Could not load decisions: {e}")

if decisions_df.empty:
    st.info("No decisions yet — run the pipeline for a stock to populate this.")
else:
    cols = st.columns(len(decisions_df))
    for col, (_, row) in zip(cols, decisions_df.iterrows()):
        color = VERDICT_COLORS.get(row["verdict"], "#9e9e9e")
        with col:
            st.markdown(f"### {row['symbol']}")
            st.markdown(
                f"<span style='background-color:{color};padding:4px 10px;"
                f"border-radius:6px;color:black;font-weight:bold'>{row['verdict']}</span>",
                unsafe_allow_html=True,
            )
            stop_loss_val = row['stop_loss']
            target_val = row['target_price']
            st.metric("Stop Loss", f"₹{stop_loss_val:.2f}" if pd.notna(stop_loss_val) else "—")
            st.metric("Target", f"₹{target_val:.2f}" if pd.notna(target_val) else "—")
st.divider()

# ---------------------------------------------------------------------------
# Drill-down
# ---------------------------------------------------------------------------
st.subheader(f"🔍 {selected_symbol} — Detail View")

# Price chart
price_df = get_price_history(selected_symbol)
if not price_df.empty:
    st.line_chart(price_df.set_index("timestamp")["close"])
else:
    st.info("No price history yet for this stock.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Technical", "Fundamentals", "Sentiment", "Prediction", "Decision Reasoning"]
)

with tab1:
    tech_df = get_technical(selected_symbol)
    if not tech_df.empty:
        st.dataframe(tech_df.T, use_container_width=True)
    else:
        st.info("No technical data yet.")

with tab2:
    fund_df = get_fundamentals(selected_symbol)
    if not fund_df.empty:
        st.dataframe(fund_df.T, use_container_width=True)
    else:
        st.info("No fundamentals data yet.")

with tab3:
    sent_df = get_sentiment(selected_symbol)
    if not sent_df.empty:
        st.dataframe(sent_df.T, use_container_width=True)
    else:
        st.info("No sentiment data yet.")

with tab4:
    pred_df = get_prediction(selected_symbol)
    if not pred_df.empty:
        st.dataframe(pred_df.T, use_container_width=True)
        st.caption("⚠️ Prediction Agent confidence is weak (~0.46-0.50 backtested accuracy). Treat as low-signal.")
    else:
        st.info("No prediction data yet.")

with tab5:
    if not decisions_df.empty and "symbol" in decisions_df.columns:
        row = decisions_df[decisions_df["symbol"] == selected_symbol]
    else:
        row = pd.DataFrame()
    if not row.empty:
        st.markdown(f"**Verdict:** {row.iloc[0]['verdict']}")
        st.write(row.iloc[0]["reasoning"] or "No reasoning text stored for this decision.")
        st.json(row.iloc[0]["signals_used"] or {})
    else:
        st.info("No decision recorded yet for this stock.")