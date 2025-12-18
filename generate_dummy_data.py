#!/usr/bin/env python3
"""
Script to generate dummy data for MLOps Dashboard
1. Inserts dummy market data into PostgreSQL
2. Sends prediction requests to FastAPI to generate metrics
"""

import requests
import psycopg2
import random
import time
from datetime import datetime, timedelta
import json

# PostgreSQL connection settings
PG_HOST = "localhost"
PG_PORT = 5433
PG_USER = "mlops_user"
PG_PASSWORD = "mlops_secure_password_123"
PG_DATABASE = "mlops_warehouse"

# FastAPI settings
FASTAPI_URL = "http://localhost:8000"

def create_table_and_insert_data():
    """Create the raw_market_data table and insert dummy data"""
    print("🐘 Connecting to PostgreSQL...")
    
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            database=PG_DATABASE
        )
        cursor = conn.cursor()
        
        # Create schema if not exists
        cursor.execute("CREATE SCHEMA IF NOT EXISTS warehouse;")
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warehouse.raw_market_data (
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
        """)
        
        print("✅ Table warehouse.raw_market_data created!")
        
        # Generate dummy data for the last hour
        print("📊 Inserting dummy market data...")
        
        base_price = 104000.0  # BTC price
        base_time = datetime.now() - timedelta(hours=1)
        
        headlines = [
            "Bitcoin breaks new resistance level as institutional interest grows",
            "Crypto market sees bullish momentum amid positive regulatory news",
            "BTC trading volume surges as whales accumulate",
            "Analysts predict continued upward trend for Bitcoin",
            "Market sentiment turns positive after Fed announcement",
            "Bitcoin ETF inflows reach new highs",
            "Crypto adoption accelerates in emerging markets",
            "DeFi protocols see increased activity",
            "Bitcoin mining difficulty reaches new peak",
            "Institutional investors increase crypto allocations"
        ]
        
        for i in range(100):
            # Simulate price movement
            price = base_price + random.uniform(-500, 500) + (i * 10)
            volume = random.uniform(1000, 5000)
            market_cap = price * 19500000  # Approximate BTC supply
            price_change = random.uniform(-2, 3)
            headline = random.choice(headlines)
            sentiment = random.uniform(0.3, 0.9)
            ingested_at = base_time + timedelta(minutes=i * 0.6)
            
            cursor.execute("""
                INSERT INTO warehouse.raw_market_data 
                (symbol, price, volume, market_cap, price_change_24h, headline, sentiment_score, ingested_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, ('BTC', price, volume, market_cap, price_change, headline, sentiment, ingested_at))
        
        conn.commit()
        print(f"✅ Inserted 100 rows of dummy market data!")
        
        # Verify data
        cursor.execute("SELECT COUNT(*) FROM warehouse.raw_market_data;")
        count = cursor.fetchone()[0]
        print(f"📊 Total records in table: {count}")
        
        cursor.execute("SELECT price FROM warehouse.raw_market_data ORDER BY ingested_at DESC LIMIT 1;")
        latest_price = cursor.fetchone()[0]
        print(f"💰 Latest BTC price: ${latest_price:,.2f}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL Error: {e}")
        return False

def send_prediction_requests():
    """Send prediction requests to FastAPI to generate metrics"""
    print("\n🚀 Sending prediction requests to FastAPI...")
    
    # First check if the API is available
    try:
        health = requests.get(f"{FASTAPI_URL}/health", timeout=5)
        if health.status_code == 200:
            print("✅ FastAPI is healthy!")
        else:
            print(f"⚠️ FastAPI health check returned: {health.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to FastAPI at port 8000. Is the model-api container running?")
        return False
    except Exception as e:
        print(f"⚠️ Health check error: {e}")
    
    # Send prediction requests
    successful_predictions = 0
    
    for i in range(20):
        try:
            # Create dummy prediction request
            data = {
                "price": 104000 + random.uniform(-1000, 1000),
                "volume": random.uniform(1000, 5000),
                "price_change_24h": random.uniform(-5, 5),
                "market_cap": random.uniform(2e12, 2.1e12),
                "sentiment_score": random.uniform(0.3, 0.9)
            }
            
            response = requests.post(
                f"{FASTAPI_URL}/predict",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                successful_predictions += 1
                result = response.json()
                print(f"  ✅ Prediction {i+1}: {result.get('prediction', 'N/A')}")
            else:
                print(f"  ⚠️ Request {i+1}: Status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"  ❌ Connection error on request {i+1}")
        except Exception as e:
            print(f"  ⚠️ Request {i+1} error: {e}")
        
        time.sleep(0.5)  # Small delay between requests
    
    print(f"\n📊 Successful predictions: {successful_predictions}/20")
    
    # Also send some feedback
    print("\n📝 Sending feedback requests...")
    for i in range(5):
        try:
            feedback_data = {
                "prediction_id": f"pred_{i}",
                "actual_value": random.choice(["bullish", "bearish", "neutral"]),
                "was_correct": random.choice([True, False])
            }
            
            response = requests.post(
                f"{FASTAPI_URL}/feedback",
                json=feedback_data,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"  ✅ Feedback {i+1} sent")
            else:
                print(f"  ⚠️ Feedback {i+1}: Status {response.status_code}")
                
        except Exception as e:
            print(f"  ⚠️ Feedback {i+1} error: {e}")
    
    return successful_predictions > 0

def main():
    print("=" * 60)
    print("🎯 MLOps Dashboard Data Generator")
    print("=" * 60)
    
    # Step 1: PostgreSQL data
    pg_success = create_table_and_insert_data()
    
    # Step 2: FastAPI predictions
    api_success = send_prediction_requests()
    
    print("\n" + "=" * 60)
    print("📋 Summary")
    print("=" * 60)
    print(f"PostgreSQL Data: {'✅ Success' if pg_success else '❌ Failed'}")
    print(f"FastAPI Metrics: {'✅ Success' if api_success else '❌ Failed'}")
    
    if pg_success:
        print("\n💡 PostgreSQL data is now available!")
        print("   Query: SELECT * FROM warehouse.raw_market_data ORDER BY ingested_at DESC LIMIT 10;")
    
    print("\n🔄 Refresh your Grafana dashboard to see the updated data!")
    print("   URL: http://localhost:3000/d/mlops-overview/mlops-pipeline-overview")

if __name__ == "__main__":
    main()
