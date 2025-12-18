# 📖 Tutorial: Running the MLOps Platform

<div align="center">

**Complete step-by-step guide to deploy and operate the Real-Time Financial Market Sentiment & Price Predictor platform.**

</div>

---

## 📋 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Starting the Platform](#3-starting-the-platform)
4. [Verifying Services](#4-verifying-services)
5. [Using the Dashboard](#5-using-the-dashboard)
6. [Running the Data Pipeline](#6-running-the-data-pipeline)
7. [Making Predictions](#7-making-predictions)
8. [Monitoring & Troubleshooting](#8-monitoring--troubleshooting)
9. [Stopping the Platform](#9-stopping-the-platform)

---

## 1. Prerequisites

### Required Software

| Software | Minimum Version | Check Command |
|----------|-----------------|---------------|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | v2.0+ | `docker compose version` |
| Git | 2.0+ | `git --version` |

### System Requirements

- **RAM:** 8GB minimum (16GB recommended)
- **Disk:** 20GB free space
- **OS:** Linux, macOS, or Windows with WSL2

### Verify Docker is Running

```bash
# Check Docker daemon status
docker info

# If Docker is not running, start it:
sudo systemctl start docker  # Linux
# or open Docker Desktop on macOS/Windows
```

---

## 2. Installation

### Clone the Repository

```bash
# Clone the project
git clone https://github.com/yourusername/engineer_mlops.git
cd engineer_mlops

# (Optional) Create environment file
cp .env.example .env
```

### Environment Configuration

Edit `.env` file if you need to customize:

```bash
# Database Configuration
POSTGRES_USER=mlops_user
POSTGRES_PASSWORD=mlops_secure_password_123
POSTGRES_DB=mlops_warehouse

# MinIO Configuration
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=minio_secure_password_123

# Airflow Configuration
AIRFLOW_ADMIN_USER=airflow
AIRFLOW_ADMIN_PASSWORD=airflow

# Grafana Configuration
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 3. Starting the Platform

### Quick Start (Recommended)

```bash
# Start all services in detached mode
docker compose up -d

# Watch the startup logs
docker compose logs -f
```

### Using Makefile Commands

```bash
# Start all services
make up

# View logs
make logs

# Check status
make status
```

### Expected Startup Time

| Service | Startup Time |
|---------|--------------|
| PostgreSQL | ~10 seconds |
| MinIO | ~5 seconds |
| Redpanda | ~30 seconds |
| Airflow | ~60 seconds |
| MLflow | ~30 seconds |
| Model API | ~30 seconds |
| Prometheus | ~5 seconds |
| Grafana | ~10 seconds |

**Total:** ~2-3 minutes for full platform startup

---

## 4. Verifying Services

### Check Container Status

```bash
# List all running containers
docker compose ps

# Expected output: All services showing "Up" status
```

### Service Health Checks

| Service | Health Check URL | Expected Response |
|---------|------------------|-------------------|
| Grafana | http://localhost:3000/api/health | `{"database": "ok"}` |
| Airflow | http://localhost:8081/health | `{"status": "healthy"}` |
| Model API | http://localhost:8000/health | `{"status": "healthy"}` |
| Prometheus | http://localhost:9095/-/healthy | `Prometheus is Healthy` |
| MinIO | http://localhost:9001 | Login page |
| Redpanda | http://localhost:8080 | Console page |

### Quick Verification Script

```bash
# Run this to verify all services
echo "Checking services..."
curl -s http://localhost:3000/api/health && echo " ✅ Grafana"
curl -s http://localhost:8081/health && echo " ✅ Airflow"
curl -s http://localhost:8000/health && echo " ✅ Model API"
curl -s http://localhost:9095/-/healthy && echo " ✅ Prometheus"
echo "All services are running!"
```

---

## 5. Using the Dashboard

### Access Grafana

1. Open browser: http://localhost:3000
2. Login with: `admin` / `admin`
3. Navigate to: **Dashboards** → **MLOps Pipeline Overview**

### Dashboard Panels Explained

| Panel | What It Shows |
|-------|---------------|
| **Pipeline Status** | Model API health (UP/DOWN) |
| **Total Predictions** | Number of active services |
| **Prediction Latency (p95)** | 95th percentile response time |
| **Feedback Received** | Total metrics collected |
| **Predictions Over Time** | Service uptime history |
| **Latency Distribution** | Scrape duration by service |
| **Data Ingestion Rate** | Kafka streaming status |
| **Database - Raw Data Count** | PostgreSQL record count |
| **Latest Price (BTC/USD)** | Real-time BTC price |

### Customize Time Range

- Click the time picker in the top right
- Select: `Last 1 hour`, `Last 6 hours`, or custom range
- Dashboard auto-refreshes every 10 seconds

---

## 6. Running the Data Pipeline

### Start the Data Producer

```bash
# Navigate to ingestion directory
cd data_engineering/ingestion

# Install dependencies
pip install -r requirements.txt

# Start the producer
python producers/producer.py --interval 10
```

### View Data in Redpanda

1. Open: http://localhost:8080
2. Click: **Topics** → **market-data**
3. View real-time messages

### Run dbt Transformations

```bash
# Navigate to dbt directory
cd data_engineering/dbt

# Install dbt dependencies
pip install dbt-postgres

# Run transformations
dbt run --profiles-dir .
```

### Trigger Airflow DAG

1. Open: http://localhost:8081
2. Login: `airflow` / `airflow`
3. Find DAG: `example_dbt_dag`
4. Toggle ON and click **Trigger DAG**

---

## 7. Making Predictions

### Using the API

```bash
# Health check
curl http://localhost:8000/health

# Make a prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "price": 104500.0,
    "volume": 2500.0,
    "price_change_24h": 2.5,
    "market_cap": 2000000000000,
    "sentiment_score": 0.75
  }'

# Submit feedback
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "prediction_id": "pred_123",
    "actual_value": "bullish",
    "was_correct": true
  }'
```

### Using Swagger UI

1. Open: http://localhost:8000/docs
2. Explore available endpoints
3. Click **Try it out** to test

---

## 8. Monitoring & Troubleshooting

### View Service Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f grafana
docker compose logs -f airflow-webserver
docker compose logs -f model-api
```

### Check Prometheus Metrics

1. Open: http://localhost:9095
2. Query: `up` to see all service statuses
3. Query: `scrape_duration_seconds` for latencies

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Port already in use | `sudo lsof -i :PORT` and kill the process |
| Container won't start | Check logs: `docker compose logs SERVICE` |
| Database connection error | Wait for PostgreSQL to be healthy |
| MinIO access denied | Verify credentials in `.env` |
| Grafana no data | Check Prometheus datasource connection |

### Restart a Service

```bash
# Restart specific service
docker compose restart grafana

# Recreate service
docker compose up -d --force-recreate grafana
```

---

## 9. Stopping the Platform

### Graceful Shutdown

```bash
# Stop all services (keeps data)
docker compose down

# Stop and remove volumes (data loss!)
docker compose down -v
```

### Using Makefile

```bash
# Stop services
make down

# Clean everything
make clean
```

### Free Up Resources

```bash
# Remove unused Docker resources
docker system prune -f

# Remove all unused volumes
docker volume prune -f
```

---

## 🔗 Quick Reference

### Service URLs

| Service | URL |
|---------|-----|
| Grafana | http://localhost:3000 |
| Airflow | http://localhost:8081 |
| MinIO | http://localhost:9001 |
| Redpanda | http://localhost:8080 |
| Prometheus | http://localhost:9095 |
| MLflow | http://localhost:5000 |
| Model API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

### Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| Grafana | admin | admin |
| Airflow | airflow | airflow |
| MinIO | minio_admin | minio_secure_password_123 |
| PostgreSQL | mlops_user | mlops_secure_password_123 |

### Useful Commands

```bash
# Start platform
docker compose up -d

# View status
docker compose ps

# View logs
docker compose logs -f

# Stop platform
docker compose down

# Restart service
docker compose restart SERVICE_NAME
```

---

<div align="center">

**Need help? Check the [README.md](README.md) for more details.**

Made with ❤️ by Fiqri

</div>
