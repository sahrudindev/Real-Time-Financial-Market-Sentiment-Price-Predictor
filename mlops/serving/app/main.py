"""
FastAPI Model Serving Application
=================================
Serves ML models from MLflow Model Registry for real-time predictions.

Features:
- Dynamic model loading from MLflow
- Prediction endpoint
- Feedback endpoint for drift monitoring
- Prometheus metrics
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import mlflow
from mlflow.tracking import MlflowClient
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# =============================================================================
# Configuration
# =============================================================================

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "crypto-price-predictor")
MLFLOW_S3_ENDPOINT_URL = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")

# Set MLflow environment for MinIO access
os.environ["MLFLOW_S3_ENDPOINT_URL"] = MLFLOW_S3_ENDPOINT_URL
os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID", "minio_admin")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY", "minio_secure_password_123")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Prometheus Metrics
# =============================================================================

PREDICTION_COUNTER = Counter(
    "predictions_total",
    "Total number of predictions made",
    ["model_version", "status"]
)

PREDICTION_LATENCY = Histogram(
    "prediction_latency_seconds",
    "Time spent processing prediction requests",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

FEEDBACK_COUNTER = Counter(
    "feedback_total",
    "Total feedback records received"
)

# =============================================================================
# Pydantic Models
# =============================================================================

class PredictionRequest(BaseModel):
    """Request model for predictions."""
    price: float = Field(..., description="Current price in USD")
    volume_24h: float = Field(..., description="24-hour trading volume")
    price_change_pct: float = Field(..., description="24-hour price change %")
    sma_10: float = Field(..., description="10-period SMA")
    sma_50: float = Field(..., description="50-period SMA")
    rsi_14: float = Field(..., description="14-period RSI")
    volatility_10: float = Field(0.0, description="10-period volatility")
    volume_ratio: float = Field(1.0, description="Volume ratio")
    sma_crossover: int = Field(0, description="SMA crossover signal (-1, 0, 1)")
    sentiment_score: float = Field(0.0, description="Sentiment score (-1 to 1)")

    class Config:
        json_schema_extra = {
            "example": {
                "price": 42500.0,
                "volume_24h": 25000000000,
                "price_change_pct": 2.5,
                "sma_10": 42300.0,
                "sma_50": 41800.0,
                "rsi_14": 55.0,
                "volatility_10": 500.0,
                "volume_ratio": 1.2,
                "sma_crossover": 1,
                "sentiment_score": 0.4
            }
        }


class PredictionResponse(BaseModel):
    """Response model for predictions."""
    predicted_price: float
    prediction_id: str
    model_version: str
    timestamp: str
    confidence_interval: Optional[Dict[str, float]] = None


class FeedbackRequest(BaseModel):
    """Request model for feedback (actual values)."""
    prediction_id: str
    actual_price: float
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    model_version: Optional[str]
    timestamp: str


# =============================================================================
# Model Manager
# =============================================================================

class ModelManager:
    """Manages MLflow model loading and versioning."""
    
    def __init__(self):
        self.model = None
        self.model_version = None
        self.model_uri = None
        self.client = None
        
    def initialize(self):
        """Initialize MLflow client and load model."""
        try:
            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            self.client = MlflowClient(MLFLOW_TRACKING_URI)
            logger.info(f"Connected to MLflow at {MLFLOW_TRACKING_URI}")
            self.load_production_model()
        except Exception as e:
            logger.error(f"Failed to initialize MLflow: {e}")
            raise
    
    def load_production_model(self):
        """Load the latest Production stage model."""
        try:
            # Try to get Production model first
            model_uri = f"models:/{MODEL_NAME}/Production"
            try:
                self.model = mlflow.pyfunc.load_model(model_uri)
                self.model_uri = model_uri
                
                # Get version info
                versions = self.client.get_latest_versions(MODEL_NAME, stages=["Production"])
                if versions:
                    self.model_version = versions[0].version
                else:
                    self.model_version = "production"
                    
                logger.info(f"Loaded Production model: {MODEL_NAME} v{self.model_version}")
                return
            except Exception:
                logger.warning("No Production model found, trying latest version...")
            
            # Fallback to latest version
            versions = self.client.search_model_versions(f"name='{MODEL_NAME}'")
            if versions:
                latest = max(versions, key=lambda x: int(x.version))
                model_uri = f"models:/{MODEL_NAME}/{latest.version}"
                self.model = mlflow.pyfunc.load_model(model_uri)
                self.model_version = latest.version
                self.model_uri = model_uri
                logger.info(f"Loaded latest model: {MODEL_NAME} v{self.model_version}")
            else:
                logger.warning(f"No model versions found for {MODEL_NAME}")
                self.model = None
                
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Make predictions using the loaded model."""
        if self.model is None:
            raise ValueError("No model loaded")
        return self.model.predict(features)
    
    def reload_model(self):
        """Reload the model (for hot reloading)."""
        logger.info("Reloading model...")
        self.load_production_model()


# Global model manager
model_manager = ModelManager()

# Feedback store (in production, use Redis or database)
feedback_store: List[Dict[str, Any]] = []

# =============================================================================
# FastAPI Application
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("Starting up Model Serving API...")
    try:
        model_manager.initialize()
    except Exception as e:
        logger.error(f"Startup failed: {e}")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="Crypto Price Predictor API",
    description="Real-time price prediction using MLflow-served models",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "service": "Crypto Price Predictor API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if model_manager.model else "degraded",
        model_loaded=model_manager.model is not None,
        model_version=model_manager.model_version,
        timestamp=datetime.utcnow().isoformat()
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """
    Make a price prediction.
    
    Returns predicted price 1 hour into the future.
    """
    import time
    start_time = time.time()
    
    if model_manager.model is None:
        PREDICTION_COUNTER.labels(
            model_version="none",
            status="error"
        ).inc()
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service is starting up or model unavailable."
        )
    
    try:
        # Prepare features DataFrame
        features = pd.DataFrame([{
            "price": request.price,
            "volume_24h": request.volume_24h,
            "price_change_pct": request.price_change_pct,
            "sma_10": request.sma_10,
            "sma_50": request.sma_50,
            "rsi_14": request.rsi_14,
            "volatility_10": request.volatility_10,
            "volume_ratio": request.volume_ratio,
            "sma_crossover": request.sma_crossover,
            "sentiment_score": request.sentiment_score,
        }])
        
        # Make prediction
        prediction = model_manager.predict(features)
        predicted_price = float(prediction[0])
        
        # Generate prediction ID
        prediction_id = f"pred_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        
        # Record metrics
        latency = time.time() - start_time
        PREDICTION_LATENCY.observe(latency)
        PREDICTION_COUNTER.labels(
            model_version=model_manager.model_version or "unknown",
            status="success"
        ).inc()
        
        return PredictionResponse(
            predicted_price=round(predicted_price, 2),
            prediction_id=prediction_id,
            model_version=model_manager.model_version or "unknown",
            timestamp=datetime.utcnow().isoformat(),
            confidence_interval={
                "lower": round(predicted_price * 0.98, 2),
                "upper": round(predicted_price * 1.02, 2)
            }
        )
        
    except Exception as e:
        PREDICTION_COUNTER.labels(
            model_version=model_manager.model_version or "unknown",
            status="error"
        ).inc()
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest, background_tasks: BackgroundTasks):
    """
    Submit actual price for drift monitoring.
    
    This endpoint collects ground truth data to compare against predictions
    for detecting model drift.
    """
    try:
        # Store feedback
        feedback_record = {
            "prediction_id": feedback.prediction_id,
            "actual_price": feedback.actual_price,
            "received_at": datetime.utcnow().isoformat(),
            "feedback_timestamp": feedback.timestamp
        }
        feedback_store.append(feedback_record)
        
        # Increment counter
        FEEDBACK_COUNTER.inc()
        
        # In production: write to database asynchronously
        # background_tasks.add_task(save_feedback_to_db, feedback_record)
        
        logger.info(f"Received feedback for {feedback.prediction_id}")
        
        return {
            "status": "received",
            "prediction_id": feedback.prediction_id,
            "message": "Feedback recorded for drift analysis"
        }
        
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feedback/stats")
async def feedback_stats():
    """Get feedback statistics for monitoring."""
    if not feedback_store:
        return {"count": 0, "message": "No feedback received yet"}
    
    return {
        "count": len(feedback_store),
        "latest": feedback_store[-1] if feedback_store else None,
        "oldest": feedback_store[0] if feedback_store else None
    }


@app.post("/model/reload")
async def reload_model():
    """Trigger model reload from MLflow."""
    try:
        model_manager.reload_model()
        return {
            "status": "success",
            "model_version": model_manager.model_version,
            "message": "Model reloaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
