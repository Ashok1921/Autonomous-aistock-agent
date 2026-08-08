from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM stocks;"))
        print("Connected successfully! Stocks table row count:", result.scalar())
except Exception as e:
    print("Connection failed:", e)