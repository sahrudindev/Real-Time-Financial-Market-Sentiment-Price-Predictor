-- Feature Engineering Model: Technical Indicators and Sentiment
-- Calculates SMA, RSI, and sentiment scores for ML training

{{
    config(
        materialized='table',
        schema='marts'
    )
}}

WITH base_data AS (
    SELECT
        id,
        event_timestamp,
        symbol,
        price,
        volume_24h,
        market_cap,
        price_change_pct,
        headline,
        source
    FROM {{ ref('stg_market_data') }}
),

-- Calculate price changes for RSI
price_changes AS (
    SELECT
        *,
        price - LAG(price) OVER (PARTITION BY symbol ORDER BY event_timestamp) AS price_change,
        LAG(price) OVER (PARTITION BY symbol ORDER BY event_timestamp) AS prev_price
    FROM base_data
),

-- Calculate gains and losses for RSI
gains_losses AS (
    SELECT
        *,
        CASE WHEN price_change > 0 THEN price_change ELSE 0 END AS gain,
        CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END AS loss
    FROM price_changes
),

-- Calculate moving averages and RSI components
with_indicators AS (
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
        
        -- Simple Moving Averages
        AVG(price) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
        ) AS sma_10,
        
        AVG(price) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
        ) AS sma_50,
        
        -- Average gains and losses for RSI (14 period)
        AVG(gain) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
        ) AS avg_gain_14,
        
        AVG(loss) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
        ) AS avg_loss_14,
        
        -- Volatility (standard deviation of price)
        STDDEV(price) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
        ) AS volatility_10,
        
        -- Volume moving average
        AVG(volume_24h) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp 
            ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
        ) AS volume_sma_10,
        
        -- Future price for prediction target (1 hour ahead = ~60 rows at 1min interval)
        LEAD(price, 60) OVER (
            PARTITION BY symbol 
            ORDER BY event_timestamp
        ) AS target_price_1h
        
    FROM gains_losses
),

-- Calculate RSI and sentiment
final AS (
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
        
        -- Moving Averages
        ROUND(sma_10::numeric, 2) AS sma_10,
        ROUND(sma_50::numeric, 2) AS sma_50,
        
        -- RSI calculation: 100 - (100 / (1 + RS))
        CASE 
            WHEN avg_loss_14 = 0 THEN 100
            WHEN avg_gain_14 = 0 THEN 0
            ELSE ROUND((100 - (100 / (1 + (avg_gain_14 / NULLIF(avg_loss_14, 0)))))::numeric, 2)
        END AS rsi_14,
        
        -- Volatility
        ROUND(volatility_10::numeric, 2) AS volatility_10,
        
        -- Volume ratio (current vs average)
        CASE 
            WHEN volume_sma_10 > 0 
            THEN ROUND((volume_24h / volume_sma_10)::numeric, 4)
            ELSE 1
        END AS volume_ratio,
        
        -- SMA crossover signal
        CASE
            WHEN sma_10 > sma_50 THEN 1
            WHEN sma_10 < sma_50 THEN -1
            ELSE 0
        END AS sma_crossover,
        
        -- Keyword-based sentiment score (-1 to 1)
        CASE
            -- Strong bullish signals
            WHEN LOWER(headline) LIKE '%surge%' 
              OR LOWER(headline) LIKE '%rally%'
              OR LOWER(headline) LIKE '%soar%'
              OR LOWER(headline) LIKE '%bullish%'
              OR LOWER(headline) LIKE '%all-time high%'
              OR LOWER(headline) LIKE '%breaks%resistance%'
            THEN 0.8
            
            -- Moderate bullish
            WHEN LOWER(headline) LIKE '%rise%'
              OR LOWER(headline) LIKE '%gain%'
              OR LOWER(headline) LIKE '%positive%'
              OR LOWER(headline) LIKE '%optimis%'
              OR LOWER(headline) LIKE '%accumula%'
            THEN 0.4
            
            -- Strong bearish signals
            WHEN LOWER(headline) LIKE '%crash%'
              OR LOWER(headline) LIKE '%plunge%'
              OR LOWER(headline) LIKE '%bearish%'
              OR LOWER(headline) LIKE '%collapse%'
              OR LOWER(headline) LIKE '%sell-off%'
            THEN -0.8
            
            -- Moderate bearish
            WHEN LOWER(headline) LIKE '%drop%'
              OR LOWER(headline) LIKE '%fall%'
              OR LOWER(headline) LIKE '%decline%'
              OR LOWER(headline) LIKE '%concern%'
              OR LOWER(headline) LIKE '%pressure%'
            THEN -0.4
            
            -- Neutral
            ELSE 0.0
        END AS sentiment_score,
        
        -- Target for ML
        ROUND(target_price_1h::numeric, 2) AS target_price_1h,
        
        -- Price return for ML
        CASE 
            WHEN price > 0 AND target_price_1h IS NOT NULL
            THEN ROUND(((target_price_1h - price) / price * 100)::numeric, 4)
            ELSE NULL
        END AS target_return_1h_pct
        
    FROM with_indicators
)

SELECT * FROM final
WHERE sma_50 IS NOT NULL  -- Ensure enough history for indicators
ORDER BY event_timestamp
