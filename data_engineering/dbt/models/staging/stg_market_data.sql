-- Staging Model: Clean and deduplicate raw market data
-- This model prepares data for feature engineering

{{
    config(
        materialized='view',
        schema='staging'
    )
}}

WITH source AS (
    SELECT
        id,
        ingested_at,
        event_timestamp,
        symbol,
        price,
        volume_24h,
        market_cap,
        price_change_24h,
        headline,
        source,
        raw_payload,
        -- Row number for deduplication
        ROW_NUMBER() OVER (
            PARTITION BY symbol, event_timestamp
            ORDER BY ingested_at DESC
        ) AS row_num
    FROM {{ source('raw', 'raw_market_data') }}
    WHERE price IS NOT NULL
      AND price > 0
      AND event_timestamp IS NOT NULL
)

SELECT
    id,
    ingested_at,
    event_timestamp,
    symbol,
    -- Ensure proper decimal precision
    CAST(price AS DECIMAL(18,2)) AS price,
    CAST(volume_24h AS DECIMAL(24,2)) AS volume_24h,
    CAST(market_cap AS DECIMAL(24,2)) AS market_cap,
    CAST(price_change_24h AS DECIMAL(10,4)) AS price_change_pct,
    headline,
    source,
    raw_payload
FROM source
WHERE row_num = 1
ORDER BY event_timestamp
