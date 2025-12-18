#!/bin/bash

# Delete existing dashboard
curl -X DELETE "http://admin:admin@localhost:3000/api/dashboards/uid/mlops-overview" 2>/dev/null

# Create new dashboard via API
curl -X POST "http://admin:admin@localhost:3000/api/dashboards/db" \
  -H "Content-Type: application/json" \
  -d '{
  "dashboard": {
    "id": null,
    "uid": "mlops-overview",
    "title": "MLOps Pipeline Overview",
    "tags": ["mlops", "crypto", "predictor"],
    "refresh": "10s",
    "panels": [
      {
        "id": 1,
        "title": "Prometheus",
        "type": "stat",
        "gridPos": {"h": 4, "w": 4, "x": 0, "y": 0},
        "targets": [{"expr": "up{job=\"prometheus\"}", "refId": "A"}],
        "fieldConfig": {"defaults": {"mappings": [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}}}, {"type": "value", "options": {"1": {"text": "UP", "color": "green"}}}], "thresholds": {"steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}}}
      },
      {
        "id": 2,
        "title": "MinIO",
        "type": "stat",
        "gridPos": {"h": 4, "w": 4, "x": 4, "y": 0},
        "targets": [{"expr": "up{job=\"minio\"}", "refId": "A"}],
        "fieldConfig": {"defaults": {"mappings": [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}}}, {"type": "value", "options": {"1": {"text": "UP", "color": "green"}}}], "thresholds": {"steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}}}
      },
      {
        "id": 3,
        "title": "Redpanda",
        "type": "stat",
        "gridPos": {"h": 4, "w": 4, "x": 8, "y": 0},
        "targets": [{"expr": "up{job=\"redpanda\"}", "refId": "A"}],
        "fieldConfig": {"defaults": {"mappings": [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}}}, {"type": "value", "options": {"1": {"text": "UP", "color": "green"}}}], "thresholds": {"steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}}}
      },
      {
        "id": 4,
        "title": "Airflow",
        "type": "stat",
        "gridPos": {"h": 4, "w": 4, "x": 12, "y": 0},
        "targets": [{"expr": "up{job=\"airflow\"}", "refId": "A"}],
        "fieldConfig": {"defaults": {"mappings": [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}}}, {"type": "value", "options": {"1": {"text": "UP", "color": "green"}}}], "thresholds": {"steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}}}
      },
      {
        "id": 5,
        "title": "Model API",
        "type": "stat",
        "gridPos": {"h": 4, "w": 4, "x": 16, "y": 0},
        "targets": [{"expr": "up{job=\"model-api\"}", "refId": "A"}],
        "fieldConfig": {"defaults": {"mappings": [{"type": "value", "options": {"0": {"text": "DOWN", "color": "red"}}}, {"type": "value", "options": {"1": {"text": "UP", "color": "green"}}}], "thresholds": {"steps": [{"color": "red", "value": null}, {"color": "green", "value": 1}]}}}
      },
      {
        "id": 6,
        "title": "Total Services",
        "type": "stat",
        "gridPos": {"h": 4, "w": 4, "x": 20, "y": 0},
        "targets": [{"expr": "count(up==1)", "refId": "A"}],
        "fieldConfig": {"defaults": {"unit": "short", "thresholds": {"steps": [{"color": "red", "value": null}, {"color": "yellow", "value": 3}, {"color": "green", "value": 5}]}}}
      },
      {
        "id": 7,
        "title": "Service Status Over Time",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
        "targets": [{"expr": "up", "legendFormat": "{{job}}", "refId": "A"}],
        "fieldConfig": {"defaults": {"custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 20}}}
      },
      {
        "id": 8,
        "title": "Scrape Duration by Job",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
        "targets": [{"expr": "scrape_duration_seconds", "legendFormat": "{{job}}", "refId": "A"}],
        "fieldConfig": {"defaults": {"unit": "s", "custom": {"drawStyle": "line", "lineWidth": 1, "fillOpacity": 10}}}
      },
      {
        "id": 9,
        "title": "MLOps Pipeline Architecture",
        "type": "text",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 12},
        "options": {"content": "# Real-Time Financial Market Sentiment & Price Predictor\n\n## Active Services\n| Service | Port | Description |\n|---------|------|-------------|\n| Redpanda | 8080 | Kafka-compatible streaming |\n| PostgreSQL | 5433 | Data warehouse |\n| MinIO | 9001 | S3-compatible storage |\n| Airflow | 8081 | Workflow orchestration |\n| Grafana | 3000 | Monitoring & visualization |\n| Prometheus | 9095 | Metrics collection |\n\n## Data Pipeline\n- Crypto price data streaming every 10 seconds to market-data topic\n- 3 MinIO buckets: raw-data, processed-data, mlflow-artifacts\n- 2 Airflow DAGs: example_dbt_dag, retrain_pipeline", "mode": "markdown"}
      }
    ],
    "time": {"from": "now-1h", "to": "now"}
  },
  "overwrite": true
}'

echo ""
echo "Dashboard updated successfully!"
