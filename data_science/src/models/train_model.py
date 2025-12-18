"""
XGBoost Model Training with MLflow Integration
==============================================
Trains a price prediction model using features from dbt transformations.

Usage:
    python train_model.py [--experiment-name crypto-predictor]
"""

import os
import sys
import argparse
from datetime import datetime
from typing import Tuple, Dict, Any

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
import mlflow
import mlflow.xgboost
from mlflow.models.signature import infer_signature
import psycopg2

# =============================================================================
# Configuration
# =============================================================================

# PostgreSQL configuration
PG_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),  # Docker PostgreSQL on 5433
    "database": os.getenv("POSTGRES_DB", "mlops_warehouse"),
    "user": os.getenv("POSTGRES_USER", "mlops_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "mlops_secure_password_123"),
}

# MLflow configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
EXPERIMENT_NAME = "crypto-price-predictor"

# Feature columns for training
FEATURE_COLUMNS = [
    "price",
    "volume_24h",
    "price_change_pct",
    "sma_10",
    "sma_50",
    "rsi_14",
    "volatility_10",
    "volume_ratio",
    "sma_crossover",
    "sentiment_score",
]

TARGET_COLUMN = "target_price_1h"

# =============================================================================
# Data Loading
# =============================================================================

def load_features_from_postgres() -> pd.DataFrame:
    """Load feature-engineered data from PostgreSQL."""
    
    query = """
    SELECT 
        event_timestamp,
        symbol,
        price,
        volume_24h,
        price_change_pct,
        sma_10,
        sma_50,
        rsi_14,
        volatility_10,
        volume_ratio,
        sma_crossover,
        sentiment_score,
        target_price_1h,
        target_return_1h_pct
    FROM marts.fct_market_features
    WHERE target_price_1h IS NOT NULL
    ORDER BY event_timestamp
    """
    
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        df = pd.read_sql(query, conn)
        conn.close()
        print(f"✓ Loaded {len(df)} records from PostgreSQL")
        return df
    except Exception as e:
        print(f"✗ Failed to load data: {e}")
        raise


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Prepare features and target for training."""
    
    # Drop rows with any NaN values
    df_clean = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])
    
    print(f"✓ After cleaning: {len(df_clean)} samples")
    
    X = df_clean[FEATURE_COLUMNS]
    y = df_clean[TARGET_COLUMN]
    
    return X, y


# =============================================================================
# Model Training
# =============================================================================

def train_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    params: Dict[str, Any]
) -> xgb.XGBRegressor:
    """Train XGBoost regressor with early stopping."""
    
    model = xgb.XGBRegressor(
        n_estimators=params.get("n_estimators", 500),
        learning_rate=params.get("learning_rate", 0.05),
        max_depth=params.get("max_depth", 6),
        min_child_weight=params.get("min_child_weight", 1),
        subsample=params.get("subsample", 0.8),
        colsample_bytree=params.get("colsample_bytree", 0.8),
        gamma=params.get("gamma", 0),
        reg_alpha=params.get("reg_alpha", 0.01),
        reg_lambda=params.get("reg_lambda", 1),
        random_state=42,
        n_jobs=-1,
        early_stopping_rounds=50,
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False
    )
    
    return model


def evaluate_model(
    model: xgb.XGBRegressor,
    X: pd.DataFrame,
    y: pd.Series,
    prefix: str = ""
) -> Dict[str, float]:
    """Calculate evaluation metrics."""
    
    y_pred = model.predict(X)
    
    metrics = {
        f"{prefix}rmse": np.sqrt(mean_squared_error(y, y_pred)),
        f"{prefix}mae": mean_absolute_error(y, y_pred),
        f"{prefix}r2": r2_score(y, y_pred),
        f"{prefix}mape": np.mean(np.abs((y - y_pred) / y)) * 100,
    }
    
    return metrics


# =============================================================================
# MLflow Integration
# =============================================================================

def setup_mlflow(experiment_name: str) -> str:
    """Setup MLflow tracking."""
    
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    
    # Create or get experiment
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(experiment_name)
    else:
        experiment_id = experiment.experiment_id
    
    mlflow.set_experiment(experiment_name)
    print(f"✓ MLflow experiment: {experiment_name}")
    
    return experiment_id


def log_to_mlflow(
    model: xgb.XGBRegressor,
    params: Dict[str, Any],
    metrics: Dict[str, float],
    X_train: pd.DataFrame,
    feature_importance: pd.DataFrame
) -> str:
    """Log model, params, and metrics to MLflow."""
    
    with mlflow.start_run() as run:
        run_id = run.info.run_id
        
        # Log parameters
        mlflow.log_params(params)
        
        # Log metrics
        mlflow.log_metrics(metrics)
        
        # Log feature importance as artifact
        importance_path = "/tmp/feature_importance.csv"
        feature_importance.to_csv(importance_path, index=False)
        mlflow.log_artifact(importance_path, "feature_analysis")
        
        # Create model signature
        signature = infer_signature(X_train, model.predict(X_train))
        
        # Log the model
        mlflow.xgboost.log_model(
            model,
            artifact_path="model",
            signature=signature,
            registered_model_name="crypto-price-predictor",
            input_example=X_train.head(5),
        )
        
        # Log additional tags
        mlflow.set_tags({
            "model_type": "XGBoost Regressor",
            "target": TARGET_COLUMN,
            "training_date": datetime.now().isoformat(),
            "features_count": len(FEATURE_COLUMNS),
        })
        
        print(f"✓ Logged to MLflow (run_id: {run_id})")
        
        return run_id


# =============================================================================
# Main Training Pipeline
# =============================================================================

def run_training_pipeline(experiment_name: str):
    """Run the complete training pipeline."""
    
    print("=" * 60)
    print("🚀 XGBoost Training Pipeline with MLflow")
    print("=" * 60)
    print()
    
    # Step 1: Setup MLflow
    print("📋 Step 1: Setting up MLflow...")
    setup_mlflow(experiment_name)
    print()
    
    # Step 2: Load data
    print("📋 Step 2: Loading features from PostgreSQL...")
    try:
        df = load_features_from_postgres()
    except Exception as e:
        print(f"\n⚠️  Could not load data from PostgreSQL.")
        print("   Make sure the dbt models have been run first.")
        print("   Run: cd data_engineering/dbt && dbt run")
        sys.exit(1)
    print()
    
    # Step 3: Prepare features
    print("📋 Step 3: Preparing features...")
    X, y = prepare_features(df)
    
    if len(X) < 5:
        print(f"\n⚠️  Not enough data for training ({len(X)} samples)")
        print("   Run the producer and consumer to collect more data.")
        sys.exit(1)
    print()
    
    # Step 4: Split data (time-series aware)
    print("📋 Step 4: Splitting data...")
    train_size = int(len(X) * 0.7)
    val_size = int(len(X) * 0.15)
    
    X_train = X[:train_size]
    y_train = y[:train_size]
    X_val = X[train_size:train_size + val_size]
    y_val = y[train_size:train_size + val_size]
    X_test = X[train_size + val_size:]
    y_test = y[train_size + val_size:]
    
    print(f"   Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
    print()
    
    # Step 5: Define hyperparameters
    params = {
        "n_estimators": 500,
        "learning_rate": 0.05,
        "max_depth": 6,
        "min_child_weight": 1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "gamma": 0,
        "reg_alpha": 0.01,
        "reg_lambda": 1,
    }
    
    # Step 6: Train model
    print("📋 Step 5: Training XGBoost model...")
    model = train_xgboost(X_train, y_train, X_val, y_val, params)
    print(f"   Best iteration: {model.best_iteration}")
    print()
    
    # Step 7: Evaluate
    print("📋 Step 6: Evaluating model...")
    train_metrics = evaluate_model(model, X_train, y_train, "train_")
    val_metrics = evaluate_model(model, X_val, y_val, "val_")
    test_metrics = evaluate_model(model, X_test, y_test, "test_")
    
    all_metrics = {**train_metrics, **val_metrics, **test_metrics}
    
    print(f"   Train RMSE: ${train_metrics['train_rmse']:.2f}")
    print(f"   Val RMSE:   ${val_metrics['val_rmse']:.2f}")
    print(f"   Test RMSE:  ${test_metrics['test_rmse']:.2f}")
    print(f"   Test R²:    {test_metrics['test_r2']:.4f}")
    print()
    
    # Step 8: Feature importance
    print("📋 Step 7: Calculating feature importance...")
    feature_importance = pd.DataFrame({
        "feature": FEATURE_COLUMNS,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)
    
    print(feature_importance.to_string(index=False))
    print()
    
    # Step 9: Log to MLflow
    print("📋 Step 8: Logging to MLflow...")
    run_id = log_to_mlflow(model, params, all_metrics, X_train, feature_importance)
    print()
    
    # Summary
    print("=" * 60)
    print("✅ Training Complete!")
    print("=" * 60)
    print(f"   MLflow Run ID: {run_id}")
    print(f"   Model registered as: crypto-price-predictor")
    print(f"   View at: {MLFLOW_TRACKING_URI}")
    print()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Train XGBoost Price Predictor")
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=EXPERIMENT_NAME,
        help="MLflow experiment name"
    )
    args = parser.parse_args()
    
    run_training_pipeline(args.experiment_name)


if __name__ == "__main__":
    main()
