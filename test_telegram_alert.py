"""
Quick standalone test for Telegram alerts.
Run: python test_telegram_alert.py
"""

from agents.telegram_alerts import send_telegram_alert

fake_decision = {
    "verdict": "BUY",
    "conviction": 0.72,
    "stop_loss": 1277.52,
    "target_price": 1348.48,
    "reasoning": "technical: score=0.75 | fundamentals: score=0.65 | sentiment: score=0.60 | prediction: score=0.55",
}

send_telegram_alert("RELIANCE", fake_decision)