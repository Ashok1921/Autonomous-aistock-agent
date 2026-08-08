from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

MODEL_NAME = "ProsusAI/finbert"

print("Loading FinBERT model (first run downloads ~400MB, please wait)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
model.eval()

LABELS = ["positive", "negative", "neutral"]


def score_headline(headline: str) -> dict:
    """
    Run FinBERT on a single headline and return the predicted sentiment
    label, confidence, and a normalized score from -1 (very negative)
    to +1 (very positive).
    """
    inputs = tokenizer(headline, return_tensors="pt", truncation=True, max_length=64)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

    scores = {LABELS[i]: float(probs[i]) for i in range(len(LABELS))}
    label = max(scores, key=scores.get)
    confidence = scores[label]

    # Normalize to a single -1 to +1 score
    normalized_score = scores["positive"] - scores["negative"]

    return {
        "headline": headline,
        "label": label,
        "confidence": round(confidence, 3),
        "score": round(normalized_score, 3),
    }


def score_headlines(headlines: list[str]) -> list[dict]:
    return [score_headline(h) for h in headlines]

def get_recent_headlines(stock_id: int, limit: int = 10) -> list[str]:
    """
    Pull the most recent news headlines for a stock from the DB.
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT headline FROM news_items
                WHERE stock_id = :stock_id
                ORDER BY fetched_at DESC
                LIMIT :limit
            """),
            {"stock_id": stock_id, "limit": limit}
        )
        return [row[0] for row in result.fetchall()]


def save_sentiment(stock_id: int, avg_score: float, avg_confidence: float, source: str = "news"):
    """
    Save an aggregated sentiment score for a stock.
    """
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO sentiment_scores (stock_id, source, score, confidence)
                VALUES (:stock_id, :source, :score, :confidence)
            """),
            {
                "stock_id": stock_id,
                "source": source,
                "score": round(avg_score, 3),
                "confidence": round(avg_confidence, 3),
            }
        )
        conn.commit()


def get_stock_id(symbol: str) -> int:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM stocks WHERE symbol = :symbol"),
            {"symbol": symbol}
        ).fetchone()
        if not result:
            raise ValueError(f"No stock found for symbol {symbol} — run the News Agent first.")
        return result[0]


from crewai.tools import tool

@tool("Sentiment Analysis Tool")
def sentiment_analysis_tool(symbol: str) -> str:
    """
    Analyzes sentiment of recent news headlines for a stock symbol using FinBERT,
    saves the aggregated score to the database, and returns a summary.
    """
    stock_id = get_stock_id(symbol)
    headlines = get_recent_headlines(stock_id)

    if not headlines:
        return f"No recent headlines found for {symbol} to analyze. Run the News Agent first."

    results = score_headlines(headlines)
    avg_score = sum(r["score"] for r in results) / len(results)
    avg_confidence = sum(r["confidence"] for r in results) / len(results)

    save_sentiment(stock_id, avg_score, avg_confidence, source="news")

    overall = "positive" if avg_score > 0.15 else "negative" if avg_score < -0.15 else "neutral"

    lines = [f"Sentiment analysis for {symbol} based on {len(headlines)} recent headlines:"]
    lines.append(f"Overall sentiment: {overall} (avg score: {avg_score:+.3f}, avg confidence: {avg_confidence:.3f})")
    lines.append("\nTop headlines analyzed:")
    for r in results[:3]:
        lines.append(f"  [{r['label']}] {r['headline']}")

    return "\n".join(lines)




if __name__ == "__main__":
    symbol = "TCS"
    result = sentiment_analysis_tool.func(symbol)
    print(result)