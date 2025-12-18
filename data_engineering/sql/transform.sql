-- Manually run dbt transformations
-- Run with: docker exec -it postgres psql -U mlops_user -d mlops_warehouse -f /tmp/transform.sql

-- =============================================
-- Create staging schema
-- =============================================
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- =============================================
-- Staging: stg_market_data
-- Clean and deduplicate raw data
-- =============================================
DROP TABLE IF EXISTS staging.stg_market_data;

CREATE TABLE staging.stg_market_data AS
WITH ranked_data AS (
    SELECT
        id,
        event_timestamp,
        symbol,
        CAST(price AS DECIMAL(18,2)) as price,
        CAST(volume_24h AS DECIMAL(24,2)) as volume_24h,
        CAST(market_cap AS DECIMAL(24,2)) as market_cap,
        CAST(price_change_24h AS DECIMAL(10,4)) as price_change_pct,
        headline,
        source,
        ingested_at,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, DATE_TRUNC('minute', event_timestamp)
            ORDER BY ingested_at DESC
        ) as row_num
    FROM warehouse.raw_market_data
    WHERE price IS NOT NULL AND price > 0
)
SELECT
    id,
    event_timestamp,
    symbol,
    price,
    volume_24h,
    market_cap,
    price_change_pct,
    headline,
    source,
    ingested_at
FROM ranked_data
WHERE row_num = 1
ORDER BY event_timestamp;

-- =============================================
-- Marts: fct_market_features
-- Calculate technical indicators and sentiment
-- =============================================
DROP TABLE IF EXISTS marts.fct_market_features;

CREATE TABLE marts.fct_market_features AS
WITH base_data AS (
    SELECT
        id,
        event_timestamp,
        symbol,
        price,
        volume_24h,
        price_change_pct,
        headline,
        source,
        ingested_at,
        -- Calculate SMAs
        AVG(price) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
        ) as sma_10,
        AVG(price) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
        ) as sma_50,
        -- Price changes for RSI
        price - LAG(price) OVER (PARTITION BY symbol ORDER BY event_timestamp) as price_change,
        -- Volatility (standard deviation)
        STDDEV(price) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
        ) as volatility_10,
        -- Volume ratio
        volume_24h / NULLIF(AVG(volume_24h) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
        ), 0) as volume_ratio,
        -- Target: future price (for training)
        LEAD(price, 60) OVER (PARTITION BY symbol ORDER BY event_timestamp) as target_price_1h
    FROM staging.stg_market_data
),
rsi_calc AS (
    SELECT
        *,
        -- Gains and losses for RSI
        CASE WHEN price_change > 0 THEN price_change ELSE 0 END as gain,
        CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END as loss
    FROM base_data
),
rsi_avg AS (
    SELECT
        *,
        AVG(gain) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
        ) as avg_gain,
        AVG(loss) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
        ) as avg_loss
    FROM rsi_calc
)
SELECT
    id,
    event_timestamp,
    symbol,
    price,
    volume_24h,
    price_change_pct,
    ROUND(sma_10::numeric, 2) as sma_10,
    ROUND(sma_50::numeric, 2) as sma_50,
    -- RSI calculation
    ROUND(
        CASE 
            WHEN avg_loss = 0 THEN 100
            ELSE 100 - (100 / (1 + (avg_gain / NULLIF(avg_loss, 0))))
        END::numeric, 2
    ) as rsi_14,
    ROUND(volatility_10::numeric, 2) as volatility_10,
    ROUND(volume_ratio::numeric, 4) as volume_ratio,
    -- SMA crossover signal
    CASE 
        WHEN sma_10 > sma_50 THEN 1
        WHEN sma_10 < sma_50 THEN -1
        ELSE 0
    END as sma_crossover,
    -- Sentiment score from headline
    CASE
        WHEN headline ILIKE '%surge%' OR headline ILIKE '%bull%' OR headline ILIKE '%high%' OR headline ILIKE '%break%' THEN 0.8
        WHEN headline ILIKE '%drop%' OR headline ILIKE '%bear%' OR headline ILIKE '%sell%' OR headline ILIKE '%pressure%' THEN -0.8
        WHEN headline ILIKE '%stable%' OR headline ILIKE '%steady%' OR headline ILIKE '%consolidate%' THEN 0.0
        ELSE 0.0
    END as sentiment_score,
    headline,
    source,
    target_price_1h,
    ROUND(((target_price_1h - price) / NULLIF(price, 0) * 100)::numeric, 4) as target_return_1h_pct
FROM rsi_avg
ORDER BY event_timestamp;

-- Show results
SELECT 'Raw data count:' as metric, COUNT(*)::text as value FROM warehouse.raw_market_data
UNION ALL
SELECT 'Staging count:', COUNT(*)::text FROM staging.stg_market_data
UNION ALL
SELECT 'Features count:', COUNT(*)::text FROM marts.fct_market_features;
