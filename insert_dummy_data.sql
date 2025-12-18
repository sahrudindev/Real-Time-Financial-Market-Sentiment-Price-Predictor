-- Create schema and table for market data
CREATE SCHEMA IF NOT EXISTS warehouse;

DROP TABLE IF EXISTS warehouse.raw_market_data;

CREATE TABLE warehouse.raw_market_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8),
    market_cap DECIMAL(30, 2),
    price_change_24h DECIMAL(10, 4),
    headline TEXT,
    sentiment_score DECIMAL(5, 4),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert 100 rows of dummy BTC data for the last hour
INSERT INTO warehouse.raw_market_data (symbol, price, volume, market_cap, price_change_24h, headline, sentiment_score, ingested_at)
SELECT 
    'BTC',
    104000 + (random() * 2000 - 1000) + (gs * 10),
    random() * 4000 + 1000,
    (104000 + (random() * 2000 - 1000)) * 19500000,
    random() * 5 - 2,
    'Bitcoin market update - Strong momentum continues ' || gs,
    random() * 0.6 + 0.3,
    NOW() - INTERVAL '1 hour' + (gs * INTERVAL '36 seconds')
FROM generate_series(1, 100) AS gs;

-- Verify data
SELECT 'Total Records: ' || COUNT(*)::text as info FROM warehouse.raw_market_data
UNION ALL
SELECT 'Latest Price: $' || ROUND(price::numeric, 2)::text FROM warehouse.raw_market_data ORDER BY ingested_at DESC LIMIT 1;
