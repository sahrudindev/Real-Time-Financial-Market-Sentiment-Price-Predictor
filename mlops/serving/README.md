# Model Serving - FastAPI

This directory contains the model serving API.

## Structure

- `app/` - FastAPI application
  - `main.py` - Application entry point
  - `api/` - API routes
  - `core/` - Configuration and dependencies
  - `models/` - Pydantic models
  - `services/` - Business logic

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --port 8000
```

## Docker

```bash
docker build -t sentiment-api .
docker run -p 8000:8000 sentiment-api
```
