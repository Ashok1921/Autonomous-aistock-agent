from sqlalchemy import create_engine, text
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT s.symbol, d.verdict, d.stop_loss, d.target_price, d.reasoning, d.signals_used
        FROM agent_decisions d
        JOIN stocks s ON s.id = d.stock_id
        WHERE s.symbol = 'RELIANCE'
        ORDER BY d.id DESC LIMIT 3
    """))
    for row in result:
        print(dict(row._mapping))
