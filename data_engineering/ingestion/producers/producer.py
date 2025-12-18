"""
Crypto Market Data Producer
===========================
Fetches real-time crypto prices from CoinGecko and produces to Redpanda.

Usage:
    python producer.py [--interval 60] [--symbol bitcoin]
"""

import json
import os
import sys
import time
import random
import argparse
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

# =============================================================================
# Configuration
# =============================================================================

REDPANDA_BROKERS = os.getenv("REDPANDA_BROKERS", "localhost:19092")
TOPIC_NAME = "market-data"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Simulated news headlines for sentiment analysis
BULLISH_HEADLINES = [
    "Bitcoin surges as institutional adoption accelerates",
    "Crypto market sees massive inflows amid ETF optimism",
    "Major bank announces Bitcoin custody service",
    "Bitcoin breaks key resistance level, bulls in control",
    "Whale accumulation signals bullish trend continuation",
    "Positive regulatory news boosts crypto market sentiment",
    "Bitcoin hash rate hits all-time high",
    "Institutional investors increase crypto allocations",
]

BEARISH_HEADLINES = [
    "Bitcoin faces selling pressure as rates rise",
    "Crypto market sees outflows amid uncertainty",
    "Regulatory concerns weigh on Bitcoin price",
    "Bitcoin drops below key support level",
    "Whale movements suggest potential sell-off",
    "Market volatility increases as traders turn cautious",
    "Mining difficulty adjustment may pressure prices",
    "Profit-taking leads to crypto market pullback",
]

NEUTRAL_HEADLINES = [
    "Bitcoin consolidates in tight range",
    "Crypto market awaits next catalyst",
    "Trading volume remains stable",
    "Bitcoin holds steady amid mixed signals",
    "Market participants await economic data",
]

# =============================================================================
# Producer Setup
# =============================================================================

def get_producer_config() -> dict:
    """Get Kafka producer configuration."""
    return {
        "bootstrap.servers": REDPANDA_BROKERS,
        "client.id": "crypto-producer",
        "acks": "all",
        "retries": 3,
        "retry.backoff.ms": 1000,
    }


def create_topic(topic_name: str, num_partitions: int = 3) -> bool:
    """Create topic if it doesn't exist."""
    admin_config = {"bootstrap.servers": REDPANDA_BROKERS}
    admin = AdminClient(admin_config)
    
    metadata = admin.list_topics(timeout=10)
    if topic_name in metadata.topics:
        print(f"✓ Topic '{topic_name}' exists")
        return True
    
    topic = NewTopic(topic_name, num_partitions=num_partitions, replication_factor=1)
    futures = admin.create_topics([topic])
    
    for name, future in futures.items():
        try:
            future.result()
            print(f"✓ Created topic '{name}'")
            return True
        except Exception as e:
            print(f"✗ Failed to create topic: {e}")
            return False
    return False


def delivery_callback(err, msg):
    """Callback for message delivery confirmation."""
    if err:
        print(f"✗ Delivery failed: {err}")
    else:
        print(f"✓ Delivered: {msg.topic()}[{msg.partition()}] @ {msg.offset()}")


# =============================================================================
# Data Fetching
# =============================================================================

def fetch_crypto_price(symbol: str = "bitcoin") -> Optional[Dict[str, Any]]:
    """Fetch crypto price from CoinGecko API with fallback to simulated data."""
    try:
        url = f"{COINGECKO_API}/simple/price"
        params = {
            "ids": symbol,
            "vs_currencies": "usd",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if symbol in data:
            return {
                "price": data[symbol].get("usd", 0),
                "volume_24h": data[symbol].get("usd_24h_vol", 0),
                "market_cap": data[symbol].get("usd_market_cap", 0),
                "price_change_24h": data[symbol].get("usd_24h_change", 0),
            }
    except requests.RequestException as e:
        # Rate limited or API error - use simulated data
        if "429" in str(e):
            print("⚠ Rate limited - using simulated data")
        else:
            print(f"✗ API error: {e}")
        return generate_simulated_data()
    except (KeyError, ValueError) as e:
        print(f"✗ Parse error: {e}")
        return generate_simulated_data()
    
    return None


# Cache for simulated price continuity
_last_price = 42000.0


def generate_simulated_data() -> Dict[str, Any]:
    """Generate realistic simulated crypto data for demo purposes."""
    global _last_price
    
    # Random walk with mean reversion
    change_pct = random.gauss(0, 1.5)  # -3% to +3% typical
    _last_price = _last_price * (1 + change_pct / 100)
    
    # Keep price in realistic range
    _last_price = max(20000, min(100000, _last_price))
    
    return {
        "price": round(_last_price, 2),
        "volume_24h": round(random.uniform(15e9, 35e9), 2),
        "market_cap": round(_last_price * 19.5e6, 2),  # ~19.5M BTC supply
        "price_change_24h": round(change_pct, 4),
    }


def generate_headline(price_change: float) -> tuple[str, str]:
    """Generate a headline based on price movement."""
    if price_change > 2:
        headline = random.choice(BULLISH_HEADLINES)
        source = "crypto_bullish_news"
    elif price_change < -2:
        headline = random.choice(BEARISH_HEADLINES)
        source = "crypto_bearish_news"
    else:
        headline = random.choice(NEUTRAL_HEADLINES)
        source = "crypto_neutral_news"
    
    return headline, source


# =============================================================================
# Main Producer Loop
# =============================================================================

def produce_market_data(
    producer: Producer,
    topic: str,
    symbol: str = "bitcoin",
    interval: int = 60
) -> None:
    """Main loop to fetch and produce market data."""
    
    symbol_display = f"{symbol.upper()}/USD"
    print(f"\n📊 Starting producer for {symbol_display}")
    print(f"   Interval: {interval}s | Topic: {topic}")
    print("-" * 50)
    
    message_count = 0
    
    while True:
        try:
            # Fetch price data
            price_data = fetch_crypto_price(symbol)
            
            if price_data:
                # Generate headline based on price change
                headline, source = generate_headline(price_data["price_change_24h"])
                
                # Build message
                message = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "symbol": symbol_display,
                    "price": round(price_data["price"], 2),
                    "volume_24h": round(price_data["volume_24h"], 2),
                    "market_cap": round(price_data["market_cap"], 2),
                    "price_change_24h": round(price_data["price_change_24h"], 4),
                    "headline": headline,
                    "source": source,
                }
                
                # Produce to Kafka
                producer.produce(
                    topic=topic,
                    key=symbol_display.encode("utf-8"),
                    value=json.dumps(message).encode("utf-8"),
                    callback=delivery_callback,
                )
                producer.poll(0)
                
                message_count += 1
                print(f"[{message_count}] ${price_data['price']:,.2f} | "
                      f"{price_data['price_change_24h']:+.2f}% | {headline[:40]}...")
            
            # Wait for next interval
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print(f"\n\n✓ Stopped. Sent {message_count} messages.")
            producer.flush(timeout=5)
            break
        except Exception as e:
            print(f"✗ Error: {e}")
            time.sleep(5)


# =============================================================================
# Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Crypto Market Data Producer")
    parser.add_argument("--interval", type=int, default=60, help="Fetch interval in seconds")
    parser.add_argument("--symbol", type=str, default="bitcoin", help="Crypto symbol (coingecko id)")
    args = parser.parse_args()
    
    print("=" * 50)
    print("🚀 Crypto Market Data Producer")
    print("=" * 50)
    
    # Create topic
    if not create_topic(TOPIC_NAME):
        print("Failed to create topic. Is Redpanda running?")
        sys.exit(1)
    
    # Initialize producer
    try:
        config = get_producer_config()
        producer = Producer(config)
        print(f"✓ Connected to {REDPANDA_BROKERS}")
    except Exception as e:
        print(f"✗ Failed to create producer: {e}")
        sys.exit(1)
    
    # Start producing
    produce_market_data(producer, TOPIC_NAME, args.symbol, args.interval)


if __name__ == "__main__":
    main()
