"""
Test Producer - Infrastructure Validation Script
================================================
This script validates that Redpanda is accessible and can receive messages.

Usage:
    python test_producer.py

Expected Output:
    - Successfully connects to Redpanda
    - Creates a test topic
    - Sends sample messages
    - Confirms delivery
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

try:
    from confluent_kafka import Producer
    from confluent_kafka.admin import AdminClient, NewTopic
except ImportError:
    print("❌ confluent-kafka not installed. Run: pip install confluent-kafka")
    sys.exit(1)


def get_config() -> dict:
    """Get Kafka producer configuration."""
    return {
        'bootstrap.servers': os.getenv('REDPANDA_BROKERS', 'localhost:19092'),
        'client.id': 'test-producer',
        'acks': 'all',
    }


def create_topic(topic_name: str, num_partitions: int = 1) -> bool:
    """Create a topic if it doesn't exist."""
    admin_config = {'bootstrap.servers': os.getenv('REDPANDA_BROKERS', 'localhost:19092')}
    admin = AdminClient(admin_config)
    
    # Check if topic exists
    metadata = admin.list_topics(timeout=10)
    if topic_name in metadata.topics:
        print(f"✅ Topic '{topic_name}' already exists")
        return True
    
    # Create topic
    topic = NewTopic(topic_name, num_partitions=num_partitions, replication_factor=1)
    futures = admin.create_topics([topic])
    
    for topic_name, future in futures.items():
        try:
            future.result()  # Wait for creation
            print(f"✅ Created topic '{topic_name}'")
            return True
        except Exception as e:
            print(f"❌ Failed to create topic '{topic_name}': {e}")
            return False


def delivery_callback(err, msg):
    """Callback for message delivery reports."""
    if err:
        print(f"❌ Message delivery failed: {err}")
    else:
        print(f"✅ Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")


def produce_test_messages(producer: Producer, topic: str, count: int = 5) -> int:
    """Produce test messages to the topic."""
    delivered = 0
    
    for i in range(count):
        # Create sample financial data message
        message = {
            "event_id": f"test-{i+1}",
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": "AAPL",
            "price": 150.00 + (i * 0.5),
            "volume": 1000 * (i + 1),
            "source": "test_producer",
            "message_type": "infrastructure_test"
        }
        
        try:
            producer.produce(
                topic=topic,
                key=message["symbol"].encode('utf-8'),
                value=json.dumps(message).encode('utf-8'),
                callback=delivery_callback
            )
            delivered += 1
        except Exception as e:
            print(f"❌ Failed to produce message {i+1}: {e}")
    
    # Wait for all messages to be delivered
    remaining = producer.flush(timeout=10)
    if remaining > 0:
        print(f"⚠️  {remaining} messages still in queue after flush")
    
    return delivered


def main():
    """Main execution function."""
    print("=" * 60)
    print("🚀 Real-Time Financial Market Predictor - Infrastructure Test")
    print("=" * 60)
    print()
    
    topic_name = "test-financial-data"
    
    # Step 1: Create topic
    print("📋 Step 1: Creating test topic...")
    if not create_topic(topic_name):
        print("❌ Failed to create topic. Is Redpanda running?")
        print("   Try: docker compose up -d redpanda")
        sys.exit(1)
    print()
    
    # Step 2: Initialize producer
    print("📋 Step 2: Initializing Kafka producer...")
    try:
        config = get_config()
        producer = Producer(config)
        print(f"✅ Producer connected to {config['bootstrap.servers']}")
    except Exception as e:
        print(f"❌ Failed to create producer: {e}")
        sys.exit(1)
    print()
    
    # Step 3: Produce test messages
    print("📋 Step 3: Producing test messages...")
    delivered = produce_test_messages(producer, topic_name, count=5)
    print()
    
    # Summary
    print("=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    print(f"   Topic:            {topic_name}")
    print(f"   Messages sent:    {delivered}")
    print(f"   Broker:           {get_config()['bootstrap.servers']}")
    print()
    
    if delivered > 0:
        print("✅ Infrastructure test PASSED!")
        print()
        print("🎯 Next Steps:")
        print("   1. View messages in Redpanda Console: http://localhost:8080")
        print("   2. Navigate to Topics → test-financial-data → Messages")
        print("   3. Start building your real producers!")
    else:
        print("❌ Infrastructure test FAILED!")
        print("   Check that Redpanda is running and accessible.")
    
    print()


if __name__ == "__main__":
    main()
