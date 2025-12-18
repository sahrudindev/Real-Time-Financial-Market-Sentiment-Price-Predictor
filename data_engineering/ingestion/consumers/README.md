# Data Engineering Consumers

This directory contains Python scripts that consume data from Redpanda topics.

## Consumers

- `base_consumer.py` - Base consumer class with common functionality
- `raw_to_lake_consumer.py` - Writes raw messages to MinIO (Phase 2)
- `raw_to_warehouse_consumer.py` - Writes structured data to PostgreSQL (Phase 2)
