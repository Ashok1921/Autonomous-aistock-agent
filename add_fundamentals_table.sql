CREATE TABLE IF NOT EXISTS fundamentals (
    id              SERIAL PRIMARY KEY,
    stock_id        INTEGER NOT NULL REFERENCES stocks(id),
    pe_ratio        NUMERIC,
    forward_pe      NUMERIC,
    eps             NUMERIC,
    peg_ratio       NUMERIC,
    debt_to_equity  NUMERIC,
    roe             NUMERIC,
    roa             NUMERIC,
    market_cap      NUMERIC,
    dividend_yield  NUMERIC,
    book_value      NUMERIC,
    price_to_book   NUMERIC,
    revenue_growth  NUMERIC,
    profit_margin   NUMERIC,
    current_ratio   NUMERIC,
    free_cashflow   NUMERIC,
    fetched_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, fetched_at)
);

CREATE INDEX IF NOT EXISTS idx_fundamentals_stock_id ON fundamentals(stock_id);