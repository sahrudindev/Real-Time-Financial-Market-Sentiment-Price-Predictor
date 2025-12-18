"""
Market Data Consumer
====================
Consumes from Redpanda 'market-data' topic and loads into PostgreSQL.

Usage:
    python consumer.py
"""

import json
import os
import sys
import signal
from datetime import datetime
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values
from confluent_kafka import Consumer, KafkaError, KafkaException

# =============================================================================
# Configuration
# =============================================================================

REDPANDA_BROKERS = os.getenv("REDPANDA_BROKERS", "localhost:19092")
TOPIC_NAME = "market-data"
CONSUMER_GROUP = "market-data-loader"

# PostgreSQL configuration
PG_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),  # Docker PostgreSQL on 5433
    "database": os.getenv("POSTGRES_DB", "mlops_warehouse"),
    "user": os.getenv("POSTGRES_USER", "mlops_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "mlops_secure_password_123"),
}

# =============================================================================
# Database Setup
# =============================================================================

CREATE_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS warehouse;
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS warehouse.raw_market_data (
    id SERIAL PRIMARY KEY,
    ingested_at TIMESTAMP DEFAULT NOW(),
    event_timestamp TIMESTAMP,
    symbol VARCHAR(20),
    price DECIMAL(18,8),
    volume_24h DECIMAL(24,2),
    market_cap DECIMAL(24,2),
    price_change_24h DECIMAL(10,4),
    headline TEXT,
    source VARCHAR(50),
    raw_payload JSONB
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_raw_market_data_symbol_ts 
ON warehouse.raw_market_data(symbol, event_timestamp);

CREATE INDEX IF NOT EXISTS idx_raw_market_data_ingested 
ON warehouse.raw_market_data(ingested_at);
"""

INSERT_SQL = """
INSERT INTO warehouse.raw_market_data 
    (event_timestamp, symbol, price, volume_24h, market_cap, 
     price_change_24h, headline, source, raw_payload)
VALUES %s
"""


def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(**PG_CONFIG)


def setup_database():
    """Create schema and table if not exists."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(CREATE_SCHEMA_SQL)
        cur.execute(CREATE_TABLE_SQL)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✓ Database schema ready")
        return True
    except Exception as e:
        print(f"✗ Database setup failed: {e}")
        return False


# =============================================================================
# Consumer Setup
# =============================================================================

def get_consumer_config() -> dict:
    """Get Kafka consumer configuration."""
    return {
        "bootstrap.servers": REDPANDA_BROKERS,
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "max.poll.interval.ms": 300000,
    }


# =============================================================================
# Message Processing
# =============================================================================

def parse_message(msg_value: bytes) -> Optional[dict]:
    """Parse JSON message from Kafka."""
    try:
        return json.loads(msg_value.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"✗ Parse error: {e}")
        return None


def process_batch(messages: list, conn) -> int:
    """Insert batch of messages into PostgreSQL."""
    if not messages:
        return 0
    
    records = []
    for msg in messages:
        # Parse timestamp
        ts = msg.get("timestamp")
        if ts:
            try:
                event_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                event_ts = datetime.utcnow()
        else:
            event_ts = datetime.utcnow()
        
        records.append((
            event_ts,
            msg.get("symbol"),
            msg.get("price"),
            msg.get("volume_24h"),
            msg.get("market_cap"),
            msg.get("price_change_24h"),
            msg.get("headline"),
            msg.get("source"),
            json.dumps(msg),  # Store full payload as JSONB
        ))
    
    try:
        cur = conn.cursor()
        execute_values(cur, INSERT_SQL, records)
        conn.commit()
        cur.close()
        return len(records)
    except Exception as e:
        print(f"✗ Insert error: {e}")
        conn.rollback()
        return 0


# =============================================================================
# Main Consumer Loop
# =============================================================================

running = True

def signal_handler(sig, frame):
    global running
    print("\n⚠ Shutdown signal received...")
    running = False


def consume_messages(batch_size: int = 100, timeout: float = 1.0):
    """Main consumer loop."""
    global running
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup database
    if not setup_database():
        sys.exit(1)
    
    # Create consumer
    try:
        config = get_consumer_config()
        consumer = Consumer(config)
        consumer.subscribe([TOPIC_NAME])
        print(f"✓ Subscribed to '{TOPIC_NAME}'")
    except Exception as e:
        print(f"✗ Consumer creation failed: {e}")
        sys.exit(1)
    
    # Get database connection
    try:
        conn = get_db_connection()
        print(f"✓ Connected to PostgreSQL")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)
    
    print("-" * 50)
    print("📥 Waiting for messages...")
    
    total_processed = 0
    batch = []
    
    try:
        while running:
            msg = consumer.poll(timeout=timeout)
            
            if msg is None:
                # No message, flush batch if exists
                if batch:
                    processed = process_batch(batch, conn)
                    total_processed += processed
                    if processed:
                        print(f"✓ Inserted {processed} records (total: {total_processed})")
                    batch = []
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())
            
            # Parse message
            data = parse_message(msg.value())
            if data:
                batch.append(data)
                
                # Process batch when full
                if len(batch) >= batch_size:
                    processed = process_batch(batch, conn)
                    total_processed += processed
                    consumer.commit(asynchronous=False)
                    if processed:
                        print(f"✓ Inserted {processed} records (total: {total_processed})")
                    batch = []
    
    except Exception as e:
        print(f"✗ Consumer error: {e}")
    
    finally:
        # Process remaining
        if batch:
            processed = process_batch(batch, conn)
            total_processed += processed
        
        consumer.close()
        conn.close()
        print(f"\n✓ Shutdown complete. Total processed: {total_processed}")


# =============================================================================
# Entry Point
# =============================================================================

def main():
    print("=" * 50)
    print("📥 Market Data Consumer")
    print("=" * 50)
    print(f"   Brokers: {REDPANDA_BROKERS}")
    print(f"   Topic: {TOPIC_NAME}")
    print(f"   Database: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}")
    print()
    
    consume_messages()


if __name__ == "__main__":
    main()
