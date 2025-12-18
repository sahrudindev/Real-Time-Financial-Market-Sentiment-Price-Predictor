# Data Engineering Ingestion Producers

This directory contains Python scripts that produce data to Redpanda (Kafka-compatible).

## Producers

- `test_producer.py` - Infrastructure validation script
- `stock_producer.py` - Real-time stock data producer (Phase 2)
- `news_producer.py` - News headlines producer (Phase 2)

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run test producer
python test_producer.py
```
