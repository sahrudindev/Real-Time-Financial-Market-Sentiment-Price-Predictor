# dbt Models

## Directory Structure

```
models/
├── staging/          # Raw data cleaning and standardization
│   ├── stg_stock_prices.sql
│   └── stg_news_headlines.sql
├── intermediate/     # Business logic joins and transformations
│   └── int_prices_with_sentiment.sql
└── marts/            # Final analytical tables
    ├── fct_hourly_sentiment.sql
    └── dim_symbols.sql
```

## Naming Conventions

- `stg_*` - Staging models (1:1 with source)
- `int_*` - Intermediate models
- `fct_*` - Fact tables
- `dim_*` - Dimension tables
