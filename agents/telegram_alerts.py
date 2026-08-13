"""
Telegram Alerts
----------------
Sends a Telegram message when the Decision Agent produces a non-HOLD verdict.
Uses the raw Bot API via requests -- no extra SDK needed.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

VERDICT_EMOJI = {
    "STRONG_BUY": "🟢🟢",
    "BUY": "🟢",
    "HOLD": "⚪",
    "SELL": "🔴",
    "STRONG_SELL": "🔴🔴",
}


def send_telegram_alert(symbol: str, decision: dict):
    """
    Sends a formatted alert for non-HOLD verdicts.
    Silently no-ops for HOLD, and fails gracefully (prints, doesn't raise)
    if the token/chat_id are missing or the request fails -- an alert
    failure should never crash the pipeline.
    """
    if not decision:
        return

    verdict = decision.get("verdict")
    if not verdict or verdict == "HOLD":
        return  # only alert on actionable verdicts

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  [WARN] Telegram alert skipped: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set in .env")
        return

    emoji = VERDICT_EMOJI.get(verdict, "")
    stop_loss = decision.get("stop_loss")
    target_price = decision.get("target_price")
    conviction = decision.get("conviction")
    reasoning = decision.get("reasoning", "")

    lines = [
        f"{emoji} *{symbol}* — *{verdict}*",
        f"Conviction: {conviction:.2f}" if conviction is not None else "Conviction: n/a",
    ]
    if stop_loss is not None:
        lines.append(f"Stop Loss: ₹{stop_loss:.2f}")
    if target_price is not None:
        lines.append(f"Target: ₹{target_price:.2f}")
    if reasoning:
        lines.append(f"\n_{reasoning}_")

    message = "\n".join(lines)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"  [OK]   Telegram alert sent for {symbol} ({verdict})")
        else:
            print(f"  [FAIL] Telegram alert for {symbol}: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"  [FAIL] Telegram alert for {symbol}: {e}")