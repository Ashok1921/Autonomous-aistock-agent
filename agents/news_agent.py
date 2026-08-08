import feedparser
from urllib.parse import quote
from sqlalchemy import create_engine, text
from config import DATABASE_URL
from datetime import datetime
from email.utils import parsedate_to_datetime
from crewai.tools import tool


engine = create_engine(DATABASE_URL)

def fetch_news(symbol: str, company_name: str = None, max_items: int = 10) -> list[dict]:
    """
    Fetch recent news headlines for a stock from Google News RSS.
    Uses company_name if provided (better results), else falls back to symbol.
    """
    query = company_name if company_name else symbol
    encoded_query = quote(f"{query} stock NSE")
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

    feed = feedparser.parse(url)

    articles = []
    for entry in feed.entries[:max_items]:
        articles.append({
            "headline": entry.title,
            "source": entry.get("source", {}).get("title", "Google News"),
            "url": entry.link,
            "published_at": entry.get("published", None),
        })

    return articles

def get_or_create_stock(symbol: str, exchange: str = "NSE") -> int:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM stocks WHERE symbol = :symbol"),
            {"symbol": symbol}
        ).fetchone()

        if result:
            return result[0]

        result = conn.execute(
            text("""
                INSERT INTO stocks (symbol, exchange)
                VALUES (:symbol, :exchange)
                RETURNING id
            """),
            {"symbol": symbol, "exchange": exchange}
        )
        conn.commit()
        return result.fetchone()[0]


def save_news(stock_id: int, articles: list[dict]):
    """
    Save fetched news articles into news_items, skipping ones already stored
    (matched by URL to avoid duplicates).
    """
    with engine.connect() as conn:
        for article in articles:
            existing = conn.execute(
                text("SELECT id FROM news_items WHERE url = :url"),
                {"url": article["url"]}
            ).fetchone()

            if existing:
                continue

            published_at = None
            if article["published_at"]:
                try:
                    published_at = parsedate_to_datetime(article["published_at"])
                except (TypeError, ValueError):
                    published_at = None

            conn.execute(
                text("""
                    INSERT INTO news_items (stock_id, headline, source, url, published_at)
                    VALUES (:stock_id, :headline, :source, :url, :published_at)
                """),
                {
                    "stock_id": stock_id,
                    "headline": article["headline"],
                    "source": article["source"],
                    "url": article["url"],
                    "published_at": published_at,
                }
            )
        conn.commit()
        
@tool("News Fetch Tool")
def news_fetch_tool(symbol: str, company_name: str = "") -> str:
    """
    Fetches recent news headlines for a stock symbol from Google News,
    saves them to the database, and returns a summary of the headlines.
    """
    articles = fetch_news(symbol, company_name=company_name or None)

    stock_id = get_or_create_stock(symbol)
    save_news(stock_id, articles)

    if not articles:
        return f"No recent news found for {symbol}."

    summary_lines = [f"Recent news for {symbol} ({len(articles)} articles):"]
    for a in articles[:5]:
        summary_lines.append(f"- {a['headline']} ({a['source']})")

    return "\n".join(summary_lines)        




if __name__ == "__main__":
    symbol = "TCS"
    news = fetch_news(symbol, company_name="Tata Consultancy Services")

    stock_id = get_or_create_stock(symbol)
    save_news(stock_id, news)

    print(f"Saved {len(news)} articles for {symbol} (stock_id={stock_id})")